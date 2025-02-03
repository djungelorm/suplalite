from __future__ import annotations

import asyncio
import ctypes
import datetime
import inspect
import logging
import ssl
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar, cast

from suplalite import encoding, network, packets, proto

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)


@dataclass
class Context:
    client: Client


##############################################################

_handlers = {}

Handler = TypeVar("Handler", bound=Callable[..., Any])  # FIXME: avoid Any and ... here


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
def register_result_b(context: Context):
    logging.debug("pong")


@supla_call(proto.Call.SC_REGISTER_CLIENT_RESULT_B)
def register_result_b(context: Context, msg: proto.TSC_RegisterClientResult_B):
    result_code = proto.ResultCode(msg.result_code)
    if result_code != proto.ResultCode.TRUE:
        raise RuntimeError(f"Register failed: {result_code.name}")
    logging.debug("registered")
    context.client._ping_timeout = msg.activity_timeout / 2
    context.client._state = context.client.State.CONNECTED


@supla_call(proto.Call.SC_REGISTER_CLIENT_RESULT_D)
def register_result_d(context: Context, msg: proto.TSC_RegisterClientResult_D):
    result_code = proto.ResultCode(msg.result_code)
    if result_code != proto.ResultCode.TRUE:
        raise RuntimeError(f"Register failed: {result_code.name}")
    logging.debug("registered")
    context.client._ping_timeout = msg.activity_timeout / 2
    context.client._state = context.client.State.CONNECTED


@supla_call(proto.Call.SC_LOCATIONPACK_UPDATE)
def locationpack_update(context: Context, msg: proto.TSC_LocationPack):
    logging.debug("location pack update")
    context.client._got_locations = True


@supla_call(proto.Call.SC_CHANNELPACK_UPDATE_D)
def channelpack_update(context: Context, msg: proto.TSC_ChannelPack_D):
    logging.debug("channel pack update")
    context.client._got_channels = True


@supla_call(proto.Call.SC_SCENE_PACK_UPDATE)
def scenepack_update(context: Context, msg: proto.TSC_ScenePack):
    logging.debug(f"scene pack update")
    context.client._got_scenes = True


@supla_call(proto.Call.SC_CHANNELVALUE_PACK_UPDATE_B)
def channelvaluepack_update(context: Context, msg: proto.TSC_ChannelValuePack_B):
    logging.debug(f"channel value pack update")


##############################################################


class Client:
    class State(Enum):
        CONNECTING = 1
        REGISTERING = 2
        CONNECTED = 3

    def __init__(
        self,
        server,
        email,
        guid,
        authkey,
        name=None,
        version=None,
        port=2016,
        secure=True,
    ):
        self._server = server
        self._port = port
        self._secure = secure
        self._email = email
        self._name = name or ""
        self._version = version or ""
        self._guid = guid
        self._authkey = authkey
        self._channels = []

        self._stream = None
        self._state = self.State.CONNECTING
        self._last_get_next = time.time()
        self._last_ping = time.time()
        self._ping_timeout = proto.ACTIVITY_TIMEOUT_MIN / 2
        self._got_locations = False
        self._got_channels = False
        self._got_scenes = False

    async def connect(self):
        if not self._secure:
            reader, writer = await asyncio.open_connection(self._server, self._port)
        else:
            ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.VerifyMode.CERT_NONE
            reader, writer = await asyncio.open_connection(
                self._server, self._port, ssl=ssl_context
            )
        self._stream = packets.PacketStream(reader, writer)

        while self._state != self.State.CONNECTED:
            await self._update()

    async def loop_forever(self):
        while True:
            await self._update()

    async def _update(self):
        if self._state == self.State.CONNECTING:
            await self._register()
            self._state = self.State.REGISTERING
            return

        if (
            self._state == self.State.CONNECTED
            and any(
                [not self._got_locations, not self._got_channels, not self._got_scenes]
            )
            and time.time() - self._last_get_next > 3
        ):
            self._last_get_next = time.time()
            self._get_next()
            return

        if (
            self._state == self.State.CONNECTED
            and time.time() - self._last_ping > self._ping_timeout
        ):
            self._last_ping = time.time()
            await self._ping()
            return

        packet = await self._stream.recv()
        self._handle_packet(packet)

    async def _register(self):
        logging.debug("registering")
        await self._stream.send(
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

    async def _ping(self):
        logging.debug("ping")
        now = time.time()
        msg = proto.TDCS_PingServer(
            proto.TimeVal(int(now), int((now - int(now)) * 1000000))
        )
        await self._stream.send(
            packets.Packet(proto.Call.DCS_PING_SERVER, encoding.encode(msg))
        )

    async def _get_next(self):
        logging.debug("get next")
        await self._stream.send(packets.Packet(proto.Call.CS_GET_NEXT, b""))

    def _handle_packet(self, packet):
        if packet.call_id not in _handlers:
            raise RuntimeError(f"Unhandled call {packet.call_id}")

        context = Context(self)
        handler, call_type = _handlers[packet.call_id]
        call_data = bytes(packet.data)
        if call_type is not None:
            call, _ = encoding.decode(call_type, call_data)
            handler(context, call)
        else:
            handler(context)


async def main():
    client = Client(
        "127.0.0.1",
        "email@email.com",
        b"\xDD\xDD\xDD\xDD\x4A\xD3\xB8\xAA\x36\x66\x21\x6F\x2A\x86\x42\x23",
        b"\xCC\xCC\xCC\xCC\xE5\x34\xD1\xA7\x06\xAC\x5F\x41\x67\x19\x89\x9E",
        "Test Client",
        port=2016,
        secure=True,
    )
    await client.connect()
    await client.loop_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
