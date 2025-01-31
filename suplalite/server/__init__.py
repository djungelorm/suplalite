from __future__ import annotations

import asyncio
import functools
import logging
from dataclasses import dataclass
from typing import Any

import tlslite  # type: ignore

from suplalite import encoding, network, proto
from suplalite.packets import Packet, PacketStream
from suplalite.server import state
from suplalite.server.events import EventContext, EventId, EventQueue

logger = logging.getLogger("suplalite")


class BaseContext:
    server: Server
    events: EventQueue
    name: str

    def __init__(self, server: Server, events: EventQueue, name: str) -> None:
        self.server = server
        self.events = events
        self.name = name

    def log(self, msg: str, level: int = logging.INFO) -> None:
        if not logger.isEnabledFor(level):  # pragma: no cover
            return
        logger.log(level=level, msg=f"{self.name} {msg}")


class ServerContext(BaseContext):
    pass


class ConnectionContext(BaseContext):
    conn: Connection
    activity_timeout: int
    # indicates whether an error occured in a handler
    error: bool

    def __init__(
        self,
        server: Server,
        events: EventQueue,
        name: str,
        conn: Connection,
    ) -> None:
        super().__init__(server, events, name)
        self.conn = conn
        self.activity_timeout = proto.ACTIVITY_TIMEOUT_MIN
        self.error = False

        self._replacement: ClientContext | DeviceContext | None = None

    def replace(self, context: ClientContext | DeviceContext) -> None:
        self._replacement = context

    @property
    def should_replace(self) -> bool:
        return self._replacement is not None

    @property
    def replacement(self) -> ClientContext | DeviceContext:
        assert self._replacement is not None
        return self._replacement


class ClientContext(ConnectionContext):
    guid: bytes
    client_id: int
    authorized: bool

    def __init__(self, context: ConnectionContext, guid: bytes, client_id: int) -> None:
        super().__init__(
            context.server,
            context.events,
            context.name,
            context.conn,
        )
        self.guid = guid
        self.client_id = client_id
        self.authorized = False


class DeviceContext(ConnectionContext):
    guid: bytes
    device_id: int

    def __init__(self, context: ConnectionContext, guid: bytes, device_id: int) -> None:
        super().__init__(
            context.server,
            context.events,
            context.name,
            context.conn,
        )
        self.guid = guid
        self.device_id = device_id


class Handler:
    pass


@dataclass
class EventHandler(Handler):
    event_context: EventContext
    event_id: EventId
    func: Any  # TODO: correct typing


@dataclass
class CallHandler(Handler):
    call_id: proto.Call
    func: Any  # TODO: correct typing
    result_id: proto.Call | None
    call_type: type[Any] | None  # TODO: correct typing


def create_supla_server(
    address: str,
    port: int,
    secure_port: int,
    certfile: str,
    keyfile: str,
    location_name: str,
    email: str,
    password: str,
    handlers: list[Handler],
) -> Server:
    return Server(
        address,
        port,
        secure_port,
        certfile,
        keyfile,
        location_name,
        email,
        password,
        handlers,
    )


class Connection:
    def __init__(
        self,
        server: Server,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        self._reader = reader
        self._writer = writer
        remote_host, remote_port = self._writer.get_extra_info("peername")
        self._context = ConnectionContext(
            server=server,
            events=EventQueue(),
            name=f"{remote_host}:{remote_port}",
            conn=self,
        )
        self._packets: PacketStream | None = None
        self._call_task: asyncio.Task[None] | None = None
        self._event_task: asyncio.Task[None] | None = None

    @property
    def proto_version(self) -> int:
        assert self._packets is not None
        return self._packets.proto_version

    async def __call__(self) -> None:
        self._context.log("connected")

        self._packets = PacketStream(self._reader, self._writer)

        self._call_task = asyncio.create_task(self._call())
        self._event_task = asyncio.create_task(self._event())

        try:
            await self._call_task
        except network.NetworkError:  # pragma: no cover
            pass
        except asyncio.exceptions.CancelledError:  # pragma: no cover
            pass

        finally:
            self._context.log("disconnected")

            # stop the event loop
            self._event_task.cancel()
            try:
                await self._event_task
            except asyncio.exceptions.CancelledError:
                pass

            # clean up server state
            # FIXME: issues here if the handler stays alive, but the device reconnects
            # prevent the new connection until the old one is cleaned up?
            if isinstance(self._context, DeviceContext):
                device_id = self._context.device_id
                async with self._context.server.state.lock:
                    await self._context.server.state.device_disconnected(device_id)
                    await self._context.server.events.add(
                        EventId.DEVICE_DISCONNECTED, (device_id,)
                    )

            if isinstance(self._context, ClientContext):
                client_id = self._context.client_id
                async with self._context.server.state.lock:
                    await self._context.server.state.client_disconnected(client_id)
                    await self._context.server.events.add(
                        EventId.CLIENT_DISCONNECTED, (client_id,)
                    )

            self._context.log("closed")

    async def _call(self) -> None:
        assert self._packets is not None
        try:
            while True:
                try:
                    packet = await asyncio.wait_for(
                        self._packets.recv(), timeout=self._context.activity_timeout
                    )
                    if packet is None:  # pragma: no cover
                        break
                    await self._handle_call(self._context, packet)
                except asyncio.exceptions.TimeoutError:  # pragma: no cover
                    self._context.log(
                        f"timed out after {self._context.activity_timeout} seconds; "
                        "closing connection"
                    )
                    break
                if self._context.error:
                    self._context.log("error; closing connection")
                    break
                if self._context.should_replace:
                    self._context = self._context.replacement
        except network.NetworkError as exc:
            self._context.log(f"network error: {exc}", logging.ERROR)
        except Exception as exc:  # pragma no cover
            logger.error(str(exc), exc_info=exc)
            raise
        finally:
            await self._packets.close()
            self._context.log("call task stopped")

    async def _event(self) -> None:
        try:
            while True:
                event = await self._context.events.get()
                await self._handle_event(*event)
        except Exception as exc:  # pragma no cover
            logger.error(str(exc), exc_info=exc)
            raise
        finally:
            self._context.log("event task stopped")

    async def _handle_call(self, context: BaseContext, packet: Packet) -> None:
        handler = self._context.server.get_call_handler(packet.call_id)
        if handler is None:
            self._context.log(f"Unhandled call {packet.call_id}")
            return
        context.log(f"handle call {packet.call_id}", level=logging.DEBUG)
        call_data = packet.data
        if handler.call_type is not None:
            call, size = encoding.decode(handler.call_type, call_data)
            assert size == len(call_data)
            async with self._context.server.state.lock:
                result = await handler.func(context, call)
        else:
            async with self._context.server.state.lock:
                result = await handler.func(context)
        if result is not None:
            assert handler.result_id is not None
            await self.send(handler.result_id, result)

    async def send(self, call_id: proto.Call, msg: Any) -> None:
        assert self._packets is not None
        self._context.log(f"send {call_id}", level=logging.DEBUG)
        await self._packets.send(Packet(call_id, encoding.encode(msg)))

    async def _handle_event(self, event_id: EventId, payload: Any) -> None:
        if isinstance(self._context, DeviceContext):
            event_context = EventContext.DEVICE
        elif isinstance(self._context, ClientContext):
            event_context = EventContext.CLIENT
        else:  # pragma: no cover
            return
        handlers = self._context.server.get_event_handlers(event_context, event_id)
        for handler in handlers:
            self._context.log(f"handle event {event_id}", level=logging.DEBUG)
            try:
                async with self._context.server.state.lock:
                    if payload is None:
                        await handler.func(self._context)
                    else:
                        await handler.func(self._context, *payload)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("event handler failed: %s", exc)


class Server:
    def __init__(
        self,
        host: str,
        port: int,
        secure_port: int,
        certfile: str,
        keyfile: str,
        location_name: str,
        email: str,
        password: str,
        handlers: list[Handler],
    ) -> None:
        self._host = host
        self._port = port
        self._secure_port = secure_port
        self._ssl_cert = self._load_cert(certfile)
        self._ssl_key = self._load_key(keyfile)
        self._location_name = location_name
        self._email = email
        self._password = password

        self._call_handlers: dict[proto.Call, CallHandler] = {}
        for handler in handlers:
            if isinstance(handler, CallHandler):
                assert handler.call_id not in self._call_handlers
                self._call_handlers[handler.call_id] = handler

        self._event_handlers: dict[tuple[EventContext, EventId], list[EventHandler]] = (
            {}
        )
        for handler in handlers:
            if isinstance(handler, EventHandler):
                key = (handler.event_context, handler.event_id)
                if key not in self._event_handlers:
                    self._event_handlers[key] = [handler]
                else:  # pragma: no cover
                    self._event_handlers[key].append(handler)

        self._server: asyncio.Server | None = None
        self._secure_server: asyncio.Server | None = None

        self._tasks: list[asyncio.Task[None]] = []

        self._state = state.ServerState()
        self._events = EventQueue()
        self._context = ServerContext(self, self._events, "server")

        self._connection_lock = asyncio.Lock()
        self._connection_count = 0

    @staticmethod
    def _load_cert(certfile: str) -> tlslite.api.X509CertChain:
        with open(certfile, encoding="utf-8") as file:
            cert = file.read()
        x509 = tlslite.api.X509()
        x509.parse(cert)
        return tlslite.api.X509CertChain([x509])

    @staticmethod
    def _load_key(keyfile: str) -> tlslite.utils.rsakey.RSAKey:
        with open(keyfile, encoding="utf-8") as file:
            key = file.read()
        return tlslite.api.parsePEMKey(key, private=True)

    @property
    def port(self) -> int:
        return self._server.sockets[0].getsockname()[1]  # type: ignore

    @property
    def secure_port(self) -> int:
        return self._secure_server.sockets[0].getsockname()[1]  # type: ignore

    @property
    def location_name(self) -> str:
        return self._location_name

    @property
    def state(self) -> state.ServerState:
        return self._state

    @property
    def events(self) -> EventQueue:
        return self._events

    async def has_connections(self) -> bool:
        async with self._connection_lock:
            return self._connection_count > 0

    async def start(self) -> None:
        self._state.server_started()

        self._server = await asyncio.start_server(
            functools.partial(self._client_connected, False), self._host, self._port
        )
        self._secure_server = await network.start_secure_server(
            functools.partial(self._client_connected, True),
            self._host,
            self._secure_port,
            self._ssl_cert,
            self._ssl_key,
            tlslite.HandshakeSettings(),
        )
        self._tasks.extend(
            (
                asyncio.create_task(self._event_loop()),
                asyncio.create_task(self._server_loop()),
                asyncio.create_task(self._secure_server_loop()),
            )
        )

        logger.info("started")

    async def stop(self) -> None:
        while await self.has_connections():
            await asyncio.sleep(0.1)
        assert self._server is not None
        self._server.close()
        await self._server.wait_closed()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.exceptions.CancelledError:
                pass
        logger.info("stopped")

    def get_call_handler(self, call_id: proto.Call) -> CallHandler | None:
        return self._call_handlers.get(call_id, None)

    def get_event_handlers(
        self, event_context: EventContext, event_id: EventId
    ) -> list[EventHandler]:
        key = (event_context, event_id)
        if key not in self._event_handlers:
            return []
        return self._event_handlers[key]

    def check_authorized(self, email: str, password: str) -> bool:
        return self._email == email and self._password == password

    async def serve_forever(self) -> None:  # pragma: no cover
        for task in self._tasks:
            await task

    async def _event_loop(self) -> None:
        try:
            logger.debug("event loop started")
            while True:
                event_id, payload = await self._events.get()

                handlers = self.get_event_handlers(EventContext.SERVER, event_id)
                for handler in handlers:
                    self._context.log(
                        f"handle event {event_id} {handler.func.__name__}",
                        level=logging.DEBUG,
                    )
                    if payload is None:  # pragma: no cover
                        await handler.func(self._context)
                    else:
                        await handler.func(self._context, *payload)

                async with self._state.lock:
                    clients = await self._state.get_clients()
                    for client in clients.values():
                        try:
                            events = await self._state.get_client_events(client.id)
                        except KeyError:
                            continue
                        await events.add(event_id, payload)

                    devices = await self._state.get_devices()
                    for device in devices.values():
                        try:
                            events = await self._state.get_device_events(device.id)
                        except KeyError:
                            continue
                        await events.add(event_id, payload)

        except Exception as exc:  # pragma: no cover
            logger.error(str(exc), exc_info=exc)
            raise
        finally:
            logger.debug("event loop stopped")

    async def _server_loop(self) -> None:
        try:
            logger.debug("server started")
            assert self._server is not None
            await self._server.serve_forever()
        except Exception as exc:  # pragma: no cover
            logger.error(str(exc), exc_info=exc)
            raise
        finally:
            logger.debug("server stopped")

    async def _secure_server_loop(self) -> None:
        try:
            logger.debug("secure server started")
            assert self._secure_server is not None
            await self._secure_server.serve_forever()
        except Exception as exc:  # pragma: no cover
            logger.error(str(exc), exc_info=exc)
            raise
        finally:
            logger.debug("secure server stopped")

    async def _client_connected(
        self, secure: bool, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        async with self._connection_lock:
            self._connection_count += 1
        try:
            if secure:
                await writer.transport._sock.do_handshake()  # type: ignore  # pylint: disable=protected-access
            await Connection(self, reader, writer)()
        except Exception as exc:  # pragma: no cover
            logger.error(str(exc), exc_info=exc)
            raise
        finally:
            # Note: coverage bug means it thinks this is not covered?!?
            async with self._connection_lock:  # pragma: no cover
                self._connection_count -= 1
