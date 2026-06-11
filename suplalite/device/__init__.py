from __future__ import annotations

import asyncio
import contextlib
import logging
import ssl
import time
from collections.abc import Callable, Coroutine
from enum import Enum
from typing import Any

from suplalite import encoding, network, proto
from suplalite.device.channels import Channel
from suplalite.packets import Packet, PacketStream

logger = logging.getLogger("suplalite.device")

# Minimum required proto version for basic device messages (excl. channels)
BASE_PROTO_VERSION = 12

# Seconds to wait for the register result before giving up and tearing down
REGISTER_TIMEOUT = 10


class DeviceError(Exception):
    pass


class DeviceState(Enum):
    CONNECTING = 1
    REGISTERING = 2
    CONNECTED = 3


class Device:
    def __init__(
        self,
        host: str,
        port: int,
        secure: bool,
        email: str,
        name: str,
        version: str,
        authkey: bytes,
        guid: bytes,
        proto_version: int = BASE_PROTO_VERSION,
    ) -> None:
        self._start_time = time.time()
        self._host = host
        self._port = port
        self._secure = secure
        self._email = email
        self._name = name
        self._version = version
        self._authkey = authkey
        self._guid = guid
        self._proto_version = proto_version

        self._channels: list[Channel] = []

        self._state = DeviceState.CONNECTING
        self._connected = asyncio.Event()
        self._ping_timeout = proto.ACTIVITY_TIMEOUT_MIN - 5
        self._last_send = time.time()

        self._lock = asyncio.Lock()
        self._packets: PacketStream | None = None
        self._tasks: list[asyncio.Task[None]] = []

    def add(self, channel: Channel) -> None:
        if self._packets is not None:
            raise DeviceError("Cannot add channels after the device has started")
        channel_number = len(self._channels)
        self._channels.append(channel)
        channel.set_device(self, channel_number)
        self._proto_version = max(self._proto_version, channel.proto_version)

    def get(self, channel_number: int) -> Channel:
        return self._channels[channel_number]

    async def start(self) -> None:
        if self._secure:  # pragma: no cover
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            try:
                reader, writer = await asyncio.open_connection(
                    self._host, self._port, ssl=ssl_context
                )
            except ConnectionRefusedError as exc:
                raise network.NetworkError("Connection refused") from exc
        else:
            reader, writer = await asyncio.open_connection(self._host, self._port)
        logger.debug("protocol version = %d", self._proto_version)
        self._packets = PacketStream(reader, writer, self._proto_version)

        logger.info("started")

        self._tasks = []
        for x in (self._message_loop(), self._task_loop()):
            self.add_task(asyncio.create_task(x))

    @property
    def connected(self) -> asyncio.Event:
        return self._connected

    @property
    def ping_timeout(self) -> float:
        return self._ping_timeout

    @ping_timeout.setter
    def ping_timeout(self, value: float) -> None:
        self._ping_timeout = value

    async def loop_forever(self) -> None:  # pragma: no cover
        await asyncio.gather(*self._tasks)

    def add_task(self, task: asyncio.Task[None]) -> None:
        self._tasks.append(task)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        # When a task exits cancel the others so the device shuts down as a whole
        for other in self._tasks:
            if other is not task and not other.done():
                other.cancel()

    async def _message_loop(self) -> None:
        try:
            logger.debug("message loop started")

            while True:
                assert self._packets is not None
                packet = await self._packets.recv()
                await self._handle_message(packet)

        except Exception:  # pragma: no cover
            logger.exception("unexpected error")
            raise
        finally:
            logger.debug("message loop stopped")

    async def _task_loop(self) -> None:
        try:
            logger.debug("task loop started")

            register_deadline: float | None = None

            while True:
                if self._state == DeviceState.CONNECTING:
                    await self._register()
                    self._state = DeviceState.REGISTERING
                    register_deadline = time.time() + REGISTER_TIMEOUT

                if self._state == DeviceState.REGISTERING:
                    assert register_deadline is not None
                    if time.time() > register_deadline:
                        raise DeviceError("Registration timed out")  # noqa: TRY301

                if (
                    self._state == DeviceState.CONNECTED
                    and time.time() - self._last_send > self._ping_timeout
                ):
                    await self._send_ping()

                await asyncio.sleep(1)

        except Exception:
            logger.exception("unexpected error")
            raise
        finally:
            logger.debug("task loop stopped")

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        try:
            for task in self._tasks:
                with contextlib.suppress(asyncio.exceptions.CancelledError):
                    await task
        finally:
            if self._packets is not None:
                await self._packets.close()
            logger.info("stopped")

    async def _send(self, packet: Packet) -> None:
        async with self._lock:
            assert self._packets is not None
            await self._packets.send(packet)
        self._last_send = time.time()

    async def _register(self) -> None:
        if len(self._channels) == 0:
            raise DeviceError("No channels")

        msg = proto.TDS_RegisterDevice_E(
            email=self._email,
            authkey=self._authkey,
            guid=self._guid,
            name=self._name,
            soft_ver=self._version,
            server_name=self._host,
            flags=proto.DeviceFlag.NONE,
            manufacturer_id=0,
            product_id=0,
            channels=[
                proto.TDS_DeviceChannel_C(
                    number=number,
                    type=channel.type,
                    action_trigger_caps=channel.action_trigger_caps,
                    default_func=channel.func,
                    flags=channel.flags,
                    value=channel.encoded_value,
                )
                for number, channel in enumerate(self._channels)
            ],
        )

        logger.debug("registering (%d channels)", len(self._channels))
        await self._send(Packet(proto.Call.DS_REGISTER_DEVICE_E, encoding.encode(msg)))

    async def _send_ping(self) -> None:
        now = time.time()
        msg = proto.TDCS_PingServer(
            now=proto.TimeVal(
                tv_sec=int(now),
                tv_usec=int((now - int(now)) * 1000000),
            )
        )
        logger.debug("ping %f,%f", msg.now.tv_sec, msg.now.tv_usec)
        await self._send(Packet(proto.Call.DCS_PING_SERVER, encoding.encode(msg)))

    async def _handle_message(self, packet: Packet) -> None:
        handlers: dict[
            proto.Call, tuple[Any, Callable[[Any], Coroutine[Any, Any, Any]]]
        ] = {
            proto.Call.SD_REGISTER_DEVICE_RESULT: (
                proto.TSD_RegisterDeviceResult,
                self._handle_register_result,
            ),
            proto.Call.CSD_GET_CHANNEL_STATE: (
                proto.TSD_ChannelStateRequest,
                self._handle_channel_state_request,
            ),
            proto.Call.SDC_PING_SERVER_RESULT: (
                proto.TSDC_PingServerResult,
                self._handle_ping_server_result,
            ),
            proto.Call.SD_CHANNEL_SET_VALUE: (
                proto.TSD_ChannelNewValue,
                self._handle_channel_new_value,
            ),
        }

        if packet.call_id in handlers:  # pragma: no branch
            msg_type, handler = handlers[packet.call_id]
            msg, size = encoding.decode(msg_type, packet.data)
            assert len(packet.data) == size
            await handler(msg)
        else:  # pragma: no cover
            raise DeviceError(f"Unhandled call {packet.call_id}")

    async def _handle_register_result(
        self, msg: proto.TSD_RegisterDeviceResult
    ) -> None:
        if msg.result_code != proto.ResultCode.TRUE:
            raise DeviceError(f"Register failed: {msg.result_code}")
        logger.debug("registered ok")
        self._ping_timeout = msg.activity_timeout - 5
        self._state = DeviceState.CONNECTED
        self._connected.set()

    async def _handle_channel_state_request(
        self, msg: proto.TSD_ChannelStateRequest
    ) -> None:
        logger.debug("channel state request")

        now = time.time()

        result = proto.TDS_ChannelState(
            receiver_id=msg.sender_id,
            channel_number=msg.channel_number,
            fields=(
                proto.ChannelStateField.UPTIME
                | proto.ChannelStateField.CONNECTIONUPTIME
            ),
            default_icon_field=0,
            ipv4=0,
            mac=b"\x00\x00\x00\x00\x00\x00",
            battery_level=0,
            battery_powered=False,
            wifi_rssi=0,
            wifi_signal_strength=0,
            bridge_node_online=False,
            bridge_node_signal_strength=0,
            uptime=int(now - self._start_time),
            connected_uptime=int(now - self._start_time),
            battery_health=0,
            last_connection_reset_cause=0,
            light_source_lifespan=0,
            light_source_operating_time=0,
        )

        logger.debug("channel state result")
        await self._send(
            Packet(proto.Call.DSC_CHANNEL_STATE_RESULT, encoding.encode(result))
        )

    async def _handle_ping_server_result(
        self, msg: proto.TSDC_PingServerResult
    ) -> None:
        logger.debug("pong %f,%f", msg.now.tv_sec, msg.now.tv_usec)

    async def _handle_channel_new_value(self, msg: proto.TSD_ChannelNewValue) -> None:
        logger.debug("channel %d new value", msg.channel_number)

        success = False
        if msg.channel_number < len(self._channels):  # pragma: no cover
            # Note: this sends a DS_DEVICE_CHANNEL_VALUE_CHANGED_C message
            # if the value is sucessfully set
            success = await self._channels[msg.channel_number].set_encoded_value(
                msg.value
            )

        if not success:  # pragma: no cover
            await self._send(
                Packet(
                    proto.Call.DS_CHANNEL_SET_VALUE_RESULT,
                    encoding.encode(
                        proto.TDS_ChannelNewValueResult(
                            channel_number=msg.channel_number,
                            sender_id=msg.sender_id,
                            success=success,
                        )
                    ),
                )
            )

    async def set_value(self, channel_number: int, value: bytes) -> None:
        if self._state != DeviceState.CONNECTED:  # pragma: no cover
            return
        msg = proto.TDS_DeviceChannelValue_C(
            channel_number=channel_number,
            offline=False,
            validity_time_sec=0,
            value=value,
        )
        logger.debug("channel %d value changed", channel_number)
        await self._send(
            Packet(
                proto.Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C,
                encoding.encode(msg),
            )
        )
