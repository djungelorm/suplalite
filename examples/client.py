from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from suplalite import encoding, packets, proto

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("example-client")


@dataclass
class Context:
    client: Client


##############################################################

Handler = TypeVar("Handler", bound=Callable[..., Any])
_handlers: dict[proto.Call, tuple[Handler, type[Any] | None]] = {}


def supla_call(call_id: proto.Call) -> Callable[[Handler], Handler]:
    def func(handler: Handler) -> Handler:
        annotations = inspect.get_annotations(handler, eval_str=True)
        call_type = None
        if "msg" in annotations:
            call_type = annotations["msg"]
        _handlers[call_id] = (handler, call_type)
        return handler

    return func


##############################################################


@supla_call(proto.Call.SDC_PING_SERVER_RESULT)
async def register_result_b(context: Context) -> None:
    logger.debug("pong")


@supla_call(proto.Call.SC_REGISTER_CLIENT_RESULT_D)
async def register_result_d(
    context: Context, msg: proto.TSC_RegisterClientResult_D
) -> None:
    result_code = proto.ResultCode(msg.result_code)
    if result_code != proto.ResultCode.TRUE:
        raise RuntimeError(f"Register failed: {result_code.name}")
    logger.debug("registered")
    context.client.ping_timeout = msg.activity_timeout / 2
    context.client.state = context.client.State.AUTHENTICATING
    await oauth_request(context)


@supla_call(proto.Call.SC_LOCATIONPACK_UPDATE)
async def locationpack_update(context: Context, msg: proto.TSC_LocationPack) -> None:
    logger.debug("location pack update")
    context.client.got_locations = msg.total_left == 0


@supla_call(proto.Call.SC_CHANNELPACK_UPDATE_E)
async def channelpack_update(context: Context, msg: proto.TSC_ChannelPack_E) -> None:
    logger.debug("channel pack update")
    context.client.got_channels = msg.total_left == 0


@supla_call(proto.Call.SC_CHANNEL_RELATION_PACK_UPDATE)
async def channelrelationpack_update(
    context: Context, msg: proto.TSC_ChannelRelationPack
) -> None:
    logger.debug("channel relation pack update")


@supla_call(proto.Call.SC_SCENE_PACK_UPDATE)
async def scenepack_update(context: Context, msg: proto.TSC_ScenePack) -> None:
    logger.debug("scene pack update")
    context.client.got_scenes = msg.total_left == 0


@supla_call(proto.Call.SC_CHANNELVALUE_PACK_UPDATE_B)
async def channelvaluepack_update(
    context: Context, msg: proto.TSC_ChannelValuePack_B
) -> None:
    logger.debug("channel value pack update")


async def oauth_request(context: Context) -> None:
    assert context.client.stream is not None
    await context.client.stream.send(
        packets.Packet(proto.Call.CS_OAUTH_TOKEN_REQUEST, b"")
    )


@supla_call(proto.Call.SC_OAUTH_TOKEN_REQUEST_RESULT)
async def oauth_result(
    context: Context, msg: proto.TSC_OAuthTokenRequestResult
) -> None:
    logger.debug("oauth result")
    context.client.state = context.client.State.CONNECTED


##############################################################


class Client:
    class State(Enum):
        CONNECTING = 1
        REGISTERING = 2
        AUTHENTICATING = 3
        CONNECTED = 4

    def __init__(
        self,
        server: str,
        email: str,
        guid: bytes,
        authkey: bytes,
        name: str | None = None,
        version: str | None = None,
        port: int = 2016,
        secure: bool = True,
    ) -> None:
        self._server = server
        self._port = port
        self._secure = secure
        self._email = email
        self._name = name or ""
        self._version = version or ""
        self._guid = guid
        self._authkey = authkey
        self._channels = []

        self.stream = None
        self.state = self.State.CONNECTING
        self._last_get_next = 0
        self._last_ping = time.time()
        self.ping_timeout = proto.ACTIVITY_TIMEOUT_MIN / 2
        self.got_locations = False
        self.got_channels = False
        self.got_scenes = False
        self._extra_get_next = 3

    async def connect(self) -> None:
        if not self._secure:
            reader, writer = await asyncio.open_connection(self._server, self._port)
        else:
            ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.VerifyMode.CERT_NONE
            reader, writer = await asyncio.open_connection(
                self._server, self._port, ssl=ssl_context
            )
        self.stream = packets.PacketStream(reader, writer)

        while self.state != self.State.CONNECTED:
            await self._update()

    async def loop_forever(self) -> None:
        while True:
            await self._update()

    async def _update(self) -> None:
        if self.state == self.State.CONNECTING:
            await self._register()
            self.state = self.State.REGISTERING
            return

        not_got_all = any(
            [not self.got_locations, not self.got_channels, self._extra_get_next > 0]
        )
        if (
            self.state == self.State.CONNECTED
            and not_got_all
            and time.time() - self._last_get_next > 0.5
        ):
            if self.got_locations and self.got_channels:
                self._extra_get_next -= 1
            self._last_get_next = time.time()
            await self._get_next()
            return

        if (
            self.state == self.State.CONNECTED
            and time.time() - self._last_ping > self.ping_timeout
        ):
            self._last_ping = time.time()
            await self._ping()
            return

        assert self.stream is not None
        if not_got_all:
            packet = None
            try:
                async with asyncio.timeout(0.5):
                    packet = await self.stream.recv()
            except TimeoutError:
                pass
            if packet is not None:
                await self._handle_packet(packet)

        else:
            packet = await self.stream.recv()
            await self._handle_packet(packet)

    async def _register(self) -> None:
        logger.debug("registering")
        assert self.stream is not None
        await self.stream.send(
            packets.Packet(
                proto.Call.CS_REGISTER_CLIENT_D,
                encoding.encode(
                    proto.TCS_RegisterClient_D(
                        self._email,
                        "",
                        self._authkey,
                        self._guid,
                        self._name,
                        self._version,
                        self._server,
                    )
                ),
            )
        )

    async def _ping(self) -> None:
        logger.debug("ping")
        assert self.stream is not None
        now = time.time()
        msg = proto.TDCS_PingServer(
            proto.TimeVal(int(now), int((now - int(now)) * 1000000))
        )
        await self.stream.send(
            packets.Packet(proto.Call.DCS_PING_SERVER, encoding.encode(msg))
        )

    async def _get_next(self) -> None:
        logger.debug("get next")
        assert self.stream is not None
        await self.stream.send(packets.Packet(proto.Call.CS_GET_NEXT, b""))

    async def _handle_packet(self, packet: packets.Packet) -> None:
        if packet.call_id not in _handlers:
            raise RuntimeError(f"Unhandled call {packet.call_id}")

        context = Context(self)
        handler, call_type = _handlers[packet.call_id]
        call_data = bytes(packet.data)
        if call_type is not None:
            call, _ = encoding.decode(call_type, call_data)
            await handler(context, call)
        else:
            await handler(context)


async def main() -> None:
    client = Client(
        "127.0.0.1",
        "email@email.com",
        b"\xdd\xdd\xdd\xdd\x4a\xd3\xb8\xaa\x36\x66\x21\x6f\x2a\x86\x42\x23",
        b"\xcc\xcc\xcc\xcc\xe5\x34\xd1\xa7\x06\xac\x5f\x41\x67\x19\x89\x9e",
        "Test Client",
        port=2016,
        secure=True,
    )
    await client.connect()
    await client.loop_forever()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
