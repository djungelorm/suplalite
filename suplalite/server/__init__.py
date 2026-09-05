from __future__ import annotations

import asyncio
import contextlib
import functools
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast

import tlslite
import tlslite.api
import tlslite.utils.rsakey
import uvicorn

from suplalite import encoding, network, proto
from suplalite.packets import Packet, PacketStream
from suplalite.server import api, state
from suplalite.server.context import (
    BaseContext,
    ClientContext,
    ConnectionContext,
    DeviceContext,
    ServerContext,
)
from suplalite.server.events import EventContext, EventId, EventQueue
from suplalite.server.handlers import CallHandler, EventHandler

logger = logging.getLogger("suplalite.server")

# How long stop() waits for connections to close of their own accord, before
# closing them itself
STOP_TIMEOUT = 10.0

# How long a connection is held open after a failed registration, before being
# closed. Matches supla-server's hold_time_on_failure.
AUTH_FAILURE_DELAY = 2.0


class Connection:
    def __init__(
        self,
        server: Server,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._context = ConnectionContext(
            server=server,
            events=EventQueue(),
            name=str(self._writer.get_extra_info("peername")),
            conn=self,
        )
        self._packets: PacketStream | None = None
        self._call_task: asyncio.Task[None] | None = None
        self._event_task: asyncio.Task[None] | None = None
        self._superseded = False

    @property
    def proto_version(self) -> int:
        assert self._packets is not None
        return self._packets.proto_version

    async def __call__(self) -> None:
        self._context.log("connected", logging.DEBUG)

        self._packets = PacketStream(self._reader, self._writer)

        self._call_task = asyncio.create_task(self._call())
        self._event_task = asyncio.create_task(self._event())

        try:
            await self._call_task
        except network.NetworkError:  # pragma: no cover
            pass
        except asyncio.exceptions.CancelledError:
            pass

        finally:
            self._context.log("disconnected", logging.DEBUG)

            # stop the event loop
            self._event_task.cancel()
            with contextlib.suppress(asyncio.exceptions.CancelledError):
                await self._event_task

            # clean up server state, unless a newer connection has already taken
            # over this connection's slot (in which case it now owns the state)
            if not self._superseded:
                if isinstance(self._context, DeviceContext):
                    device_id = self._context.device_id
                    async with self._context.server.state.lock:
                        self._context.server.state.device_disconnected(device_id)
                        await self._context.server.events.add(
                            EventId.DEVICE_DISCONNECTED, (device_id,)
                        )
                    self._context.log("device removed", logging.DEBUG)

                if isinstance(self._context, ClientContext):
                    client_id = self._context.client_id
                    async with self._context.server.state.lock:
                        self._context.server.state.client_disconnected(client_id)
                        await self._context.server.events.add(
                            EventId.CLIENT_DISCONNECTED, (client_id,)
                        )
                    self._context.log("client removed", logging.DEBUG)

            self._context.log("closed")

    def supersede(self) -> None:
        # Terminate this connection because a newer one has registered with the
        # same GUID and taken over its slot in the server state. Cancel the tasks
        # so the connection tears down promptly; the disconnect cleanup is
        # skipped so the replacement is left intact.
        self._superseded = True
        if self._call_task is not None:  # pragma: no branch
            self._call_task.cancel()
        if self._event_task is not None:  # pragma: no branch
            self._event_task.cancel()

    async def _call(self) -> None:
        assert self._packets is not None
        try:
            while True:
                try:
                    proto_version = self._packets.proto_version
                    packet = await asyncio.wait_for(
                        self._packets.recv(), timeout=self._context.activity_timeout
                    )
                    if proto_version != self._packets.proto_version:
                        self._context.log(
                            "proto version changed: "
                            f"{proto_version} -> {self._packets.proto_version}",
                            logging.DEBUG,
                        )
                    await self._handle_call(self._context, packet)
                except asyncio.exceptions.TimeoutError:  # pragma: no cover
                    self._context.log(
                        f"timed out after {self._context.activity_timeout} seconds; "
                        "closing connection"
                    )
                    break
                finally:
                    if self._context.should_replace:
                        self._context = self._context.replacement
                if self._context.error:
                    self._context.log("error; closing connection", logging.WARNING)
                    # Note: supla-server holds a failed registration for
                    # hold_time_on_failure before dropping the peer. Wait after
                    # the reply rather than before it (as supla-server does for
                    # devices, though not for clients) because the handler and
                    # its reply run under the global state lock -- waiting
                    # there would stall every other connection.
                    await asyncio.sleep(self._context.close_delay)
                    break
        except network.NetworkError as exc:
            self._context.log(f"network error: {exc}", logging.ERROR)
        except Exception:  # pragma no cover
            logger.exception("unexpected error")
            raise
        finally:
            await self._packets.close()
            self._context.log("call task stopped", logging.DEBUG)

    async def _event(self) -> None:
        try:
            while True:
                event = await self._context.events.get()
                await self._handle_event(*event)
        except Exception:
            # An exception escaping the per-handler try in _handle_event kills
            # the event task. Close the connection rather than leaving the call
            # task running against a connection that can no longer send events.
            logger.exception("unexpected error")
            self._context.log("event task failed; closing connection", logging.ERROR)
            self.close()
        finally:
            self._context.log("event task stopped", logging.DEBUG)

    def close(self) -> None:
        # Terminate this connection. If it is serving, cancel the call task and
        # let the teardown in __call__ clean up the server state as for any
        # other disconnect (unlike supersede(), which deliberately skips it).
        # If it has not started serving yet -- e.g. it is still in the TLS
        # handshake -- there is no task to cancel, so close the socket instead.
        if self._call_task is not None:
            self._call_task.cancel()
        else:
            self._writer.close()

    async def _handle_call(self, context: BaseContext, packet: Packet) -> None:
        handler = self._context.server.get_call_handler(packet.call_id)
        if handler is None:
            context.log(f"Unhandled call {packet.call_id}", level=logging.ERROR)
            return
        context.log(f"handle call {packet.call_id}", level=logging.DEBUG)
        call_data = packet.data
        call = None
        if handler.call_type is not None:
            call, size = encoding.decode(handler.call_type, call_data)
            assert size == len(call_data)
        await context.server.events.add(
            EventId.REQUEST, (context, packet.call_id, call)
        )
        async with self._context.server.state.lock:
            if call is None:
                result = await handler.func(context)
            else:
                result = await handler.func(context, call)
            if result is not None:
                assert handler.result_id is not None
                await context.server.events.add(
                    EventId.RESPONSE, (context, handler.result_id, result)
                )
                # Note: send the response while holding the state lock
                # so it is serialised with event-handler sends
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
                    await handler.handle_event(self._context, payload)
            except Exception:
                logger.exception("event handler failed")


class Server:
    def __init__(
        self,
        listen_host: str,
        host: str,
        port: int,
        secure_port: int,
        api_port: int,
        certfile: Path,
        keyfile: Path,
        location_name: str,
        email: str,
        password: str,
        device_auth: bool = True,
        client_auth: bool = True,
        auth_failure_delay: float = AUTH_FAILURE_DELAY,
    ) -> None:

        self._listen_host = listen_host
        self._host = host
        self._port = port
        self._secure_port = secure_port
        self._api_port = api_port
        self._ssl_certfile = certfile
        self._ssl_keyfile = keyfile
        self._location_name = location_name
        self._email = email
        self._password = password
        self._device_auth = device_auth
        self._client_auth = client_auth
        self._auth_failure_delay = auth_failure_delay

        # Import here to break cyclic dependency
        from suplalite.server.handlers import (  # noqa: PLC0415
            get_handlers,
        )

        handlers = get_handlers()
        self._call_handlers: dict[proto.Call, CallHandler] = {}
        for handler in handlers:
            if isinstance(handler, CallHandler):
                assert handler.call_id not in self._call_handlers
                self._call_handlers[handler.call_id] = handler

        self._event_handlers: dict[
            tuple[EventContext, EventId], list[EventHandler]
        ] = {}
        for handler in handlers:
            if isinstance(handler, EventHandler):
                key = (handler.event_context, handler.event_id)
                if key not in self._event_handlers:
                    self._event_handlers[key] = [handler]
                else:  # pragma: no cover
                    self._event_handlers[key].append(handler)

        self._server: asyncio.Server | None = None
        self._secure_server: asyncio.Server | None = None
        self._api_server: uvicorn.Server | None = None

        self._api = api.create(self)
        self._api_config = uvicorn.Config(
            self._api,
            host=listen_host,
            port=api_port,
            ssl_certfile=str(certfile),
            ssl_keyfile=str(keyfile),
            log_config=None,
        )

        self._tasks: list[asyncio.Task[None]] = []

        self._state = state.ServerState()
        self._events = EventQueue()
        self._context = ServerContext(self, self._events, "server")

        self._connection_lock = asyncio.Lock()
        self._connections: set[Connection] = set()
        self._no_connections = asyncio.Event()
        self._no_connections.set()

    async def _load_cert(self) -> tlslite.api.X509CertChain:
        x509 = tlslite.api.X509()
        x509.parse(await asyncio.to_thread(self._ssl_certfile.read_text))
        return tlslite.api.X509CertChain([x509])  # type: ignore[no-untyped-call]

    async def _load_key(self) -> tlslite.utils.rsakey.RSAKey:
        return tlslite.api.parsePEMKey(  # type: ignore[no-untyped-call]
            await asyncio.to_thread(self._ssl_keyfile.read_text), private=True
        )

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        assert self._server is not None
        return cast("int", self._server.sockets[0].getsockname()[1])

    @property
    def secure_port(self) -> int:
        assert self._secure_server is not None
        return cast("int", self._secure_server.sockets[0].getsockname()[1])

    @property
    def api_port(self) -> int:
        assert self._api_server is not None
        for server in self._api_server.servers:
            for socket in server.sockets:  # pragma: no branch
                return cast("int", socket.getsockname()[1])
        raise RuntimeError  # pragma: no cover

    @property
    def location_name(self) -> str:
        return self._location_name

    @property
    def device_auth(self) -> bool:
        return self._device_auth

    @property
    def auth_failure_delay(self) -> float:
        return self._auth_failure_delay

    @property
    def state(self) -> state.ServerState:
        return self._state

    @property
    def events(self) -> EventQueue:
        return self._events

    def _check_config(self) -> None:
        # A device with no authkey could never register, so say so at start up
        # rather than silently rejecting it when it first connects
        if not self._device_auth:
            return
        for device in self._state.get_devices().values():
            if not self._state.has_device_authkey(device.id):
                raise ValueError(
                    f"device {device.name!r} has no authkey; set one or "
                    "construct the server with device_auth=False"
                )

    async def start(self) -> None:
        self._check_config()
        self._state.server_started()

        self._server = await asyncio.start_server(
            functools.partial(self._client_connected, False),  # noqa: FBT003
            self._listen_host,
            self._port,
        )
        self._secure_server = await network.start_secure_server(
            functools.partial(self._client_connected, True),  # noqa: FBT003
            self._listen_host,
            self._secure_port,
            await self._load_cert(),
            await self._load_key(),
            tlslite.HandshakeSettings(),
        )
        self._api_server = uvicorn.Server(self._api_config)
        self._tasks.extend(
            (
                asyncio.create_task(self._event_loop()),
                asyncio.create_task(self._server_loop()),
                asyncio.create_task(self._secure_server_loop()),
                asyncio.create_task(self._api_server.serve()),
            )
        )

        while not self._api_server.started:  # noqa: ASYNC110
            await asyncio.sleep(0)

        logger.info("started")

    # Note: ASYNC109 suggests the caller wraps the call in asyncio.timeout
    # instead, but the timeout is what paces the shutdown steps below
    async def stop(self, timeout: float | None = STOP_TIMEOUT) -> None:  # noqa: ASYNC109
        assert self._server is not None
        assert self._secure_server is not None
        assert self._api_server is not None

        # Stop accepting first, so that a peer reconnecting while we shut down
        # cannot join the set of connections we are waiting on -- one accepted
        # after the connections have been closed below would be left open
        self._server.close()
        self._secure_server.close()

        # Give connections a chance to close themselves, then close whatever is
        # left; a single wedged connection must not block shutdown forever
        if not await self._wait_for_connections(timeout):
            logger.warning("timed out waiting for connections to close; closing them")
            await self._close_connections()
            if not await self._wait_for_connections(timeout):
                logger.error("connections still open; shutting down anyway")

        closed = await self._wait_closed(self._server, timeout)
        secure_closed = await self._wait_closed(self._secure_server, timeout)
        if not (closed and secure_closed):
            logger.error("timed out waiting for connection handlers to finish")
        await self._api_server.shutdown()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.exceptions.CancelledError):
                await task
        logger.info("stopped")

    async def _wait_for_connections(self, timeout: float | None) -> bool:  # noqa: ASYNC109
        # Wait for all connections to close, returning False if timed out
        try:
            await asyncio.wait_for(self._no_connections.wait(), timeout)
        except asyncio.exceptions.TimeoutError:
            return False
        return True

    async def _wait_closed(
        self,
        server: asyncio.Server,
        timeout: float | None,  # noqa: ASYNC109
    ) -> bool:
        # Note: since Python 3.12.1 wait_closed() also waits for the connection
        # handlers to finish, so it has to be bounded too -- otherwise a
        # connection that refused to close would block shutdown here instead
        try:
            await asyncio.wait_for(server.wait_closed(), timeout)
        except asyncio.exceptions.TimeoutError:
            return False
        return True

    async def _close_connections(self) -> None:
        async with self._connection_lock:
            connections = list(self._connections)
        for connection in connections:
            connection.close()

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

    async def serve_forever(self) -> None:
        for task in self._tasks:  # pragma: no branch
            await task

    @contextlib.asynccontextmanager
    async def running(self) -> AsyncGenerator[None, None]:
        task = asyncio.create_task(self.serve_forever())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _event_loop(self) -> None:
        try:
            logger.debug("event loop started")
            while True:
                event_id, payload = await self._events.get()
                # Note: an exception escaping the per-handler try below would
                # otherwise kill the event loop, silently stopping event
                # dispatch for the whole server. Log it and carry on.
                try:
                    await self._dispatch_event(event_id, payload)
                except Exception:
                    logger.exception("event dispatch failed")

        except Exception:  # pragma: no cover
            logger.exception("unexpected error")
            raise
        finally:
            logger.debug("event loop stopped")

    async def _dispatch_event(self, event_id: EventId, payload: Any) -> None:
        handlers = self.get_event_handlers(EventContext.SERVER, event_id)
        for handler in handlers:
            self._context.log(
                f"handle event {event_id} {handler.func.__name__}",
                logging.DEBUG,
            )
            try:
                async with self._context.server.state.lock:
                    await handler.handle_event(self._context, payload)
            except Exception:  # pragma: no cover
                logger.exception("event handler failed")
        async with self._state.lock:
            clients = self._state.get_clients()
            for client in clients.values():
                try:
                    events = self._state.get_client_events(client.id)
                except KeyError:
                    continue
                await events.add(event_id, payload)

            devices = self._state.get_devices()
            for device in devices.values():
                try:
                    events = self._state.get_device_events(device.id)
                except KeyError:
                    continue
                await events.add(event_id, payload)

    async def _server_loop(self) -> None:
        try:
            logger.debug("server started")
            assert self._server is not None
            await self._server.serve_forever()
        except Exception:  # pragma: no cover
            logger.exception("unexpected error")
            raise
        finally:
            logger.debug("server stopped")

    async def _secure_server_loop(self) -> None:
        try:
            logger.debug("secure server started")
            assert self._secure_server is not None
            await self._secure_server.serve_forever()
        except Exception:  # pragma: no cover
            logger.exception("unexpected error")
            raise
        finally:
            logger.debug("secure server stopped")

    async def _client_connected(
        self, secure: bool, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        connection = Connection(self, reader, writer)
        async with self._connection_lock:
            self._connections.add(connection)
            self._no_connections.clear()
        try:
            if secure:
                await cast("Any", writer.transport)._sock.do_handshake()  # noqa: SLF001
            await connection()
        except Exception:  # pragma: no cover
            logger.exception("unexpected error")
            raise
        finally:
            # Note: coverage bug means it thinks this is not covered?!?
            async with self._connection_lock:  # pragma: no cover
                self._connections.discard(connection)
                if len(self._connections) == 0:
                    self._no_connections.set()
