import asyncio
import base64
import logging
import re
import ssl
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp
import pytest

from suplalite import encoding, network, proto
from suplalite.packets import Packet, PacketStream
from suplalite.server import Connection as ServerConnection
from suplalite.server import Server, state
from suplalite.server.context import ServerContext
from suplalite.server.events import EventContext, EventId
from suplalite.server.handlers import EventHandler, event_handler
from suplalite.utils import to_hex

from .conftest import (
    access_id,
    access_id_password,
    client_authkey,
    client_email,
    client_guid,
    client_names,
    device_authkey,
    device_guid,
    make_server,
)

proto.CHANNELPACK_MAXCOUNT = 5
proto.ACTIVITY_TIMEOUT_DEFAULT = 30


logger = logging.getLogger("server-test")


@event_handler(EventContext.SERVER, EventId.DEVICE_CONNECTED)
async def device_connected(context: ServerContext, device_id: int) -> None:
    logger.info("DEVICE_CONNECTED %d", device_id)


@event_handler(EventContext.SERVER, EventId.DEVICE_CONNECTED)
async def device_connected_with_extra(
    context: ServerContext,
    device_id: int,
    extra: str | None = None,
) -> None:
    logger.info("DEVICE_CONNECTED %d %s", device_id, extra or "none")


@event_handler(EventContext.SERVER, EventId.DEVICE_DISCONNECTED)
async def device_disconnected(context: ServerContext, device_id: int) -> None:
    logger.info("DEVICE_DISCONNECTED %d", device_id)


@event_handler(EventContext.SERVER, EventId.CHANNEL_REGISTER_VALUE)
async def channel_register_value(
    context: ServerContext,
    channel_id: int,
    value: bytes,
) -> None:
    logger.info("CHANNEL_REGISTER_VALUE %d %s", channel_id, to_hex(value))


@event_handler(EventContext.SERVER, EventId.CHANNEL_VALUE_CHANGED)
async def channel_value_changed(
    context: ServerContext,
    channel_id: int,
    value: bytes,
) -> None:
    logger.info("CHANNEL_VALUE_CHANGED %d %s", channel_id, to_hex(value))


@event_handler(EventContext.SERVER, EventId.CHANNEL_SET_VALUE)
async def channel_set_value(
    context: ServerContext,
    channel_id: int,
    value: bytes,
) -> None:
    logger.info("CHANNEL_SET_VALUE %d %s", channel_id, to_hex(value))


@event_handler(EventContext.SERVER, EventId.CLIENT_CONNECTED)
async def client_connected(context: ServerContext, client_id: int) -> None:
    logger.info("CLIENT_CONNECTED %d", client_id)


@event_handler(EventContext.SERVER, EventId.CLIENT_DISCONNECTED)
async def client_disconnected(context: ServerContext, client_id: int) -> None:
    logger.info("CLIENT_DISCONNECTED %d", client_id)


@asynccontextmanager
async def open_connection(
    server: Server, secure: bool = True
) -> AsyncGenerator[PacketStream, None]:
    port = server.secure_port if secure else server.port
    ssl_context = None
    if secure:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    reader, writer = await asyncio.open_connection("127.0.0.1", port, ssl=ssl_context)
    stream = PacketStream(reader, writer)
    try:
        yield stream
    finally:
        await stream.close()


@dataclass
class Connection:
    stream: PacketStream


@dataclass
class Device(Connection):
    pass


@asynccontextmanager
async def open_device(
    server: Server, device_id: int, secure: bool = True
) -> AsyncGenerator[Device, None]:
    async with open_connection(server, secure) as device:
        await register_device(device, device_id)
        yield Device(device)


@dataclass
class Client(Connection):
    client_id: int
    location_pack: proto.TSC_LocationPack
    channel_packs: list[proto.TSC_ChannelPack_E]
    scene_pack: proto.TSC_ScenePack


@asynccontextmanager
async def open_client(
    server: Server, name: str, secure: bool = True
) -> AsyncGenerator[Client, None]:
    async with open_connection(server, secure) as stream:
        client_id, location_pack, channel_packs, scene_pack = await register_client(
            stream, name
        )
        yield Client(stream, client_id, location_pack, channel_packs, scene_pack)


def register_device_message(device_id: int) -> proto.TDS_RegisterDevice_E:
    manufacturer_id = 0
    product_id = 0
    channels: list[proto.TDS_DeviceChannel_C] = []
    if device_id == 1:
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=0,
                type=proto.ChannelType.RELAY,
                action_trigger_caps=proto.ActionCap.TURN_ON | proto.ActionCap.TURN_OFF,
                default_func=proto.ChannelFunc.POWERSWITCH,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=1,
                type=proto.ChannelType.THERMOMETER,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.THERMOMETER,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=2,
                type=proto.ChannelType.RELAY,
                action_trigger_caps=proto.ActionCap.TURN_ON | proto.ActionCap.TURN_OFF,
                default_func=proto.ChannelFunc.POWERSWITCH,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
    elif device_id == 2:
        manufacturer_id = 7
        product_id = 1
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=0,
                type=proto.ChannelType.DIMMER,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.DIMMER,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
    elif device_id == 3:
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=0,
                type=proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.GENERAL_PURPOSE_MEASUREMENT,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=1,
                type=proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.GENERAL_PURPOSE_MEASUREMENT,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
    elif device_id == 4:
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=0,
                type=proto.ChannelType.RELAY,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.LIGHTSWITCH,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=1,
                type=proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.GENERAL_PURPOSE_MEASUREMENT,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=2,
                type=proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.GENERAL_PURPOSE_MEASUREMENT,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
    elif device_id == 5:
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=0,
                type=proto.ChannelType.RELAY,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.POWERSWITCH,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=1,
                type=proto.ChannelType.THERMOMETER,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.THERMOMETER,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=2,
                type=proto.ChannelType.HUMIDITYSENSOR,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.HUMIDITY,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=3,
                type=proto.ChannelType.HUMIDITYANDTEMPSENSOR,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.HUMIDITYANDTEMPERATURE,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=4,
                type=proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.GENERAL_PURPOSE_MEASUREMENT,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=5,
                type=proto.ChannelType.DIMMER,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.DIMMER,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=6,
                type=proto.ChannelType.RGBLEDCONTROLLER,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.RGBLIGHTING,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
        channels.append(
            proto.TDS_DeviceChannel_C(
                number=7,
                type=proto.ChannelType.DIMMERANDRGBLED,
                action_trigger_caps=proto.ActionCap.NONE,
                default_func=proto.ChannelFunc.DIMMERANDRGBLIGHTING,
                flags=proto.ChannelFlag.CHANNELSTATE,
                value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
        )
    else:
        raise NotImplementedError  # pragma: no cover

    return proto.TDS_RegisterDevice_E(
        email="email@example.com",
        guid=device_guid[device_id],
        authkey=device_authkey[device_id],
        name=f"Device #{device_id}",
        soft_ver="1.2.3",
        server_name="localhost",
        flags=proto.DeviceFlag.NONE,
        manufacturer_id=manufacturer_id,
        product_id=product_id,
        channels=channels,
    )


async def register_device(stream: PacketStream, device_id: int) -> int:
    call = register_device_message(device_id)
    await stream.send(Packet(proto.Call.DS_REGISTER_DEVICE_E, encoding.encode(call)))
    packet = await stream.recv()
    assert packet.call_id == proto.Call.SD_REGISTER_DEVICE_RESULT
    result, _ = encoding.decode(proto.TSD_RegisterDeviceResult, packet.data)
    assert result.result_code == proto.ResultCode.TRUE

    return device_id


async def register_client(
    stream: PacketStream, name: str
) -> tuple[
    int,
    proto.TSC_LocationPack,
    list[proto.TSC_ChannelPack_E],
    proto.TSC_ScenePack,
]:
    call = proto.TCS_RegisterClient_D(
        email=client_email,
        password="password123",
        guid=client_guid(name),
        authkey=client_authkey(name),
        name=name,
        soft_ver="1.2.3",
        server_name="localhost",
    )
    await stream.send(Packet(proto.Call.CS_REGISTER_CLIENT_D, encoding.encode(call)))

    # register response
    packet = await stream.recv()
    assert packet.call_id == proto.Call.SC_REGISTER_CLIENT_RESULT_D
    result, _ = encoding.decode(proto.TSC_RegisterClientResult_D, packet.data)
    assert result.result_code == proto.ResultCode.TRUE
    client_id = result.client_id

    # location update
    packet = await stream.recv()
    assert packet.call_id == proto.Call.SC_LOCATIONPACK_UPDATE
    location_pack, _ = encoding.decode(proto.TSC_LocationPack, packet.data)

    # get channels
    channel_packs: list[proto.TSC_ChannelPack_E] = []
    while True:
        # send get next
        await stream.send(Packet(proto.Call.CS_GET_NEXT))

        # channel update
        packet = await stream.recv()
        assert packet.call_id == proto.Call.SC_CHANNELPACK_UPDATE_E
        channel_pack, _ = encoding.decode(proto.TSC_ChannelPack_E, packet.data)
        channel_packs.append(channel_pack)
        if channel_pack.total_left == 0:
            break

    # send get next
    await stream.send(Packet(proto.Call.CS_GET_NEXT))

    # channel relations update
    packet = await stream.recv()
    assert packet.call_id == proto.Call.SC_CHANNEL_RELATION_PACK_UPDATE

    # send get next
    await stream.send(Packet(proto.Call.CS_GET_NEXT))

    # scene update
    packet = await stream.recv()
    assert packet.call_id == proto.Call.SC_SCENE_PACK_UPDATE
    scene_pack, _ = encoding.decode(proto.TSC_ScenePack, packet.data)

    return client_id, location_pack, channel_packs, scene_pack


async def ping(stream: PacketStream) -> None:
    now = time.time()
    call = proto.TDCS_PingServer(
        proto.TimeVal(tv_sec=int(now), tv_usec=int((now - int(now)) * 1000000))
    )
    await stream.send(Packet(proto.Call.DCS_PING_SERVER, encoding.encode(call)))
    packet = await stream.recv()
    assert packet.call_id == proto.Call.SDC_PING_SERVER_RESULT


def test_state_guid_lookup() -> None:
    # devices and clients are keyed by guid; check the lookups round-trip
    # and that distinct guids stay distinct
    server_state = state.ServerState()

    device_id = server_state.add_device("device-1", device_guid[1])
    assert server_state.get_device_id(device_guid[1]) == device_id
    assert server_state.add_device("device-2", device_guid[2]) != device_id
    assert server_state.get_device_id(device_guid[2]) != device_id
    with pytest.raises(KeyError):
        server_state.get_device_id(device_guid[3])

    client_guid = b"\x01" + b"\x00" * 15
    other_client_guid = b"\x02" + b"\x00" * 15
    client_id = server_state.add_client(client_guid)
    # re-registering with the same guid returns the existing client
    assert server_state.add_client(client_guid) == client_id
    assert server_state.add_client(other_client_guid) != client_id


def test_state_client_credentials() -> None:
    server_state = state.ServerState()

    guid = b"\x01" + b"\x00" * 15
    authkey = b"\x02" + b"\x00" * 15
    client_id = server_state.add_client_credentials(
        "Client@Example.com ", guid, authkey
    )

    # a configured client keeps its id when it registers
    assert server_state.add_client(guid) == client_id
    # and a dynamically created one gets a distinct id
    assert server_state.add_client(b"\x03" + b"\x00" * 15) != client_id

    assert server_state.check_client_credentials(guid, "client@example.com", authkey)
    # the email is matched case insensitively, ignoring surrounding whitespace
    assert server_state.check_client_credentials(guid, " Client@Example.COM", authkey)
    assert not server_state.check_client_credentials(guid, "other@example.com", authkey)
    assert not server_state.check_client_credentials(
        guid, "client@example.com", b"\xff" * 16
    )
    # a guid that was never configured is not in the allowlist at all
    with pytest.raises(KeyError):
        server_state.check_client_credentials(
            b"\x03" + b"\x00" * 15, "client@example.com", authkey
        )


def test_state_device_authkey() -> None:
    server_state = state.ServerState()

    authkey = b"\x01" * 16
    with_key = server_state.add_device("device-1", device_guid[1], authkey)
    without_key = server_state.add_device("device-2", device_guid[2])

    assert server_state.has_device_authkey(with_key)
    assert server_state.check_device_authkey(with_key, authkey)
    assert not server_state.check_device_authkey(with_key, b"\xff" * 16)

    assert not server_state.has_device_authkey(without_key)
    with pytest.raises(KeyError):
        server_state.check_device_authkey(without_key, authkey)


def test_auth_is_off_by_default() -> None:
    # Note: authentication is opt-in, so a configuration written for an earlier
    # version keeps working unchanged
    server = Server(
        listen_host="127.0.0.1",
        host="127.0.0.1",
        port=0,
        secure_port=0,
        api_port=0,
        certfile=Path("ssl/server.cert"),
        keyfile=Path("ssl/server.key"),
        location_name="Test",
        email="email@email.com",
        password="password123",
    )
    assert not server.device_auth
    assert not server.client_auth


@pytest.mark.asyncio
async def test_start_rejects_device_without_authkey() -> None:
    # a device with no authkey could never register, so starting must fail
    server = make_server(device_auth=True, with_authkeys=False)
    with pytest.raises(ValueError, match="device 'device-1' has no authkey"):
        await server.start()


@pytest.mark.asyncio
@pytest.mark.parametrize("with_authkeys", [True, False])
async def test_start_without_device_auth(with_authkeys: bool) -> None:
    # without device auth the authkeys are not needed, or checked
    server = make_server(device_auth=False, with_authkeys=with_authkeys)
    await server.start()
    await server.stop()


@pytest.mark.asyncio
async def test_start_with_device_auth() -> None:
    server = make_server(device_auth=True, with_authkeys=True)
    await server.start()
    await server.stop()


def test_state_access_id() -> None:
    server_state = state.ServerState()
    server_state.add_access_id(42, "access-id-password")

    assert server_state.check_access_id_password(42, "access-id-password")
    assert not server_state.check_access_id_password(42, "wrong-password")
    with pytest.raises(KeyError):
        server_state.check_access_id_password(7, "access-id-password")


@pytest.mark.asyncio
@pytest.mark.parametrize("device_id", [1, 2, 3])
@pytest.mark.parametrize("secure", [True, False])
async def test_register_device(
    server: Server, device_id: int, secure: bool, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, device_id, secure):
        info = server.state.get_device(device_id)
        assert info.online
    assert re.search(r"device\[device-[0-9]+\] registered", caplog.text) is not None


@pytest.mark.asyncio
async def test_register_device_events(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1):
        pass
    await asyncio.sleep(0.5)
    assert "[server-test] CHANNEL_REGISTER_VALUE 1 0000000000000000" in caplog.text
    assert "[server-test] CHANNEL_REGISTER_VALUE 2 0000000000000000" in caplog.text
    assert "[server-test] CHANNEL_REGISTER_VALUE 3 0000000000000000" in caplog.text
    assert "[server-test] DEVICE_CONNECTED 1" in caplog.text
    assert "[server-test] DEVICE_CONNECTED 1 none" in caplog.text
    assert "[server-test] DEVICE_DISCONNECTED 1" in caplog.text


@pytest.mark.asyncio
async def test_event_with_extra(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    await server.events.add(EventId.DEVICE_CONNECTED, (42, "foo"))
    await asyncio.sleep(0.5)
    assert "[server-test] DEVICE_CONNECTED 42 foo" in caplog.text


async def do_register_device_invalid(
    stream: PacketStream,
    call: proto.TDS_RegisterDevice_E,
    expected: proto.ResultCode,
) -> None:
    await stream.send(
        Packet(
            proto.Call.DS_REGISTER_DEVICE_E,
            encoding.encode(call),
        )
    )
    packet = await stream.recv()
    assert packet.call_id == proto.Call.SD_REGISTER_DEVICE_RESULT
    result, _ = encoding.decode(proto.TSD_RegisterDeviceResult, packet.data)
    assert result.result_code == expected

    # Check server closes the connection
    with pytest.raises(network.NetworkError):
        await stream.recv()


@pytest.mark.asyncio
async def test_register_device_invalid_guid(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.guid = b"\xff" * 16
        await do_register_device_invalid(
            stream, call, proto.ResultCode.REGISTRATION_DISABLED
        )
    assert "device not found with guid ffffffffffffffffffffffffffffffff" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_zero_guid(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.guid = b"\x00" * 16
        await do_register_device_invalid(stream, call, proto.ResultCode.GUID_ERROR)
    assert "device sent an empty guid" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_zero_authkey(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.authkey = b"\x00" * 16
        await do_register_device_invalid(stream, call, proto.ResultCode.AUTHKEY_ERROR)
    assert "device sent an empty authkey" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_wrong_authkey(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.authkey = b"\xff" * 16
        await do_register_device_invalid(stream, call, proto.ResultCode.BAD_CREDENTIALS)
    # Note: unlike a client's, the authkey a device sent is not logged -- it is
    # configured on the server, so there is nothing to learn from it
    assert (
        "incorrect authkey for device with guid 01000000000000000000000000000000"
        in caplog.text
    )
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("authkey", [b"\x00" * 16, b"\xff" * 16])
async def test_register_device_without_device_auth(authkey: bytes) -> None:
    # with device auth off the authkey is ignored, empty or not
    server = make_server(device_auth=False)
    await server.start()
    try:
        async with open_connection(server) as stream:
            call = register_device_message(1)
            call.authkey = authkey
            await stream.send(
                Packet(proto.Call.DS_REGISTER_DEVICE_E, encoding.encode(call))
            )
            packet = await stream.recv()
            assert packet.call_id == proto.Call.SD_REGISTER_DEVICE_RESULT
            result, _ = encoding.decode(proto.TSD_RegisterDeviceResult, packet.data)
            assert result.result_code == proto.ResultCode.TRUE
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_register_device_without_device_auth_still_checks_guid() -> None:
    # the guid must still be one of the configured devices
    server = make_server(device_auth=False)
    await server.start()
    try:
        async with open_connection(server) as stream:
            call = register_device_message(1)
            call.guid = b"\xff" * 16
            await do_register_device_invalid(
                stream, call, proto.ResultCode.REGISTRATION_DISABLED
            )
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_register_device_failure_delay() -> None:
    # a failed registration is held open before the connection is closed
    delay = 0.5
    server = make_server()
    server._auth_failure_delay = delay  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    await server.start()
    try:
        async with open_connection(server) as stream:
            call = register_device_message(1)
            call.authkey = b"\xff" * 16
            start = time.time()
            await stream.send(
                Packet(proto.Call.DS_REGISTER_DEVICE_E, encoding.encode(call))
            )

            # the result is sent immediately; the wait is before the close
            packet = await stream.recv()
            assert packet.call_id == proto.Call.SD_REGISTER_DEVICE_RESULT
            assert time.time() - start < delay

            with pytest.raises(network.NetworkError):
                await stream.recv()
            assert time.time() - start >= delay
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_register_device_invalid_manufacturer_id(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.manufacturer_id = 16
        await do_register_device_invalid(
            stream, call, proto.ResultCode.CHANNEL_CONFLICT
        )
    assert "manufacturer id mismatch; expected 0 got 16" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_invalid_product_id(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.product_id = 42
        await do_register_device_invalid(
            stream, call, proto.ResultCode.CHANNEL_CONFLICT
        )
    assert "product id mismatch; expected 0 got 42" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_wrong_number_of_channels(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.channels = call.channels[:1]
        await do_register_device_invalid(
            stream, call, proto.ResultCode.CHANNEL_CONFLICT
        )
    assert "incorrect number of channels; expected 3 got 1" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_invalid_channel_number(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.channels[0].number = 10
        await do_register_device_invalid(
            stream, call, proto.ResultCode.CHANNEL_CONFLICT
        )
    assert "incorrect channel number" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_invalid_channel_type(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.channels[1].type = proto.ChannelType.RELAY
        await do_register_device_invalid(
            stream, call, proto.ResultCode.CHANNEL_CONFLICT
        )
    assert (
        "incorrect type for channel number 1; "
        "expected ChannelType.THERMOMETER got ChannelType.RELAY" in caplog.text
    )
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_invalid_channel_func(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.channels[0].default_func = proto.ChannelFunc.THERMOMETER
        await do_register_device_invalid(
            stream, call, proto.ResultCode.CHANNEL_CONFLICT
        )
    assert (
        "incorrect function for channel number 0; "
        "expected ChannelFunc.POWERSWITCH got ChannelFunc.THERMOMETER" in caplog.text
    )
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_invalid_channel_flags(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.channels[0].flags = (
            proto.ChannelFlag.RS_AUTO_CALIBRATION | proto.ChannelFlag.ZWAVE_BRIDGE
        )
        await do_register_device_invalid(
            stream, call, proto.ResultCode.CHANNEL_CONFLICT
        )
    assert (
        "incorrect flags for channel number 0; "
        "expected ChannelFlag.CHANNELSTATE"
        " got ChannelFlag.ZWAVE_BRIDGE|RS_AUTO_CALIBRATION" in caplog.text
    )
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_twice_replaces_connection(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as first:
        await register_device(first, 1)
        assert server.state.get_device(1).online

        async with open_connection(server) as second:
            await register_device(second, 1)

            # the device stays online, now owned by the new connection
            assert server.state.get_device(1).online

            # the server terminates the displaced (stale) connection
            with pytest.raises(network.NetworkError):
                await first.recv()

            # the replacement connection is fully functional
            await ping(second)

    assert "device[device-1] registered" in caplog.text
    assert "device already connected; replacing existing connection" in caplog.text
    assert "error; closing connection" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [[], ["without-scenes"]], indirect=True)
@pytest.mark.parametrize("secure", [True, False])
async def test_register_client(  # noqa: PLR0915
    server: Server, secure: bool, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server, secure) as client:
        _, location_pack, channel_packs, scene_pack = await register_client(
            client, "Test Client"
        )

        # location update
        assert len(location_pack.items) == 1
        assert location_pack.items[0].id == 1
        assert location_pack.items[0].caption == "Test"

        # channel update
        assert len(channel_packs) == 4
        assert len(channel_packs[0].items) == 5
        assert len(channel_packs[1].items) == 5
        assert len(channel_packs[2].items) == 5
        assert len(channel_packs[3].items) == 2

        assert channel_packs[0].items[0].caption == "Relay"
        assert channel_packs[0].items[0].id == 1
        assert channel_packs[0].items[0].device_id == 1
        assert channel_packs[0].items[0].type == proto.ChannelType.RELAY
        assert channel_packs[0].items[0].alt_icon == 0
        assert channel_packs[0].items[0].user_icon == 0
        assert channel_packs[0].items[0].default_config_crc32 == 0

        assert channel_packs[0].items[1].caption == "Thermometer"
        assert channel_packs[0].items[1].id == 2
        assert channel_packs[0].items[1].device_id == 1
        assert channel_packs[0].items[1].type == proto.ChannelType.THERMOMETER
        assert channel_packs[0].items[1].alt_icon == 0
        assert channel_packs[0].items[1].user_icon == 0
        assert channel_packs[0].items[1].default_config_crc32 == 420107693

        assert channel_packs[0].items[2].caption == "Relay2"
        assert channel_packs[0].items[2].id == 3
        assert channel_packs[0].items[2].device_id == 1
        assert channel_packs[0].items[2].type == proto.ChannelType.RELAY
        assert channel_packs[0].items[2].alt_icon == 0
        assert channel_packs[0].items[2].user_icon == 0
        assert channel_packs[0].items[2].default_config_crc32 == 0

        assert channel_packs[0].items[3].caption == "Lights"
        assert channel_packs[0].items[3].id == 4
        assert channel_packs[0].items[3].device_id == 2
        assert channel_packs[0].items[3].type == proto.ChannelType.DIMMER
        assert channel_packs[0].items[3].alt_icon == 1
        assert channel_packs[0].items[3].user_icon == 0
        assert channel_packs[0].items[3].default_config_crc32 == 0

        assert channel_packs[0].items[4].caption == "Measurement 1"
        assert channel_packs[0].items[4].id == 5
        assert channel_packs[0].items[4].device_id == 3
        assert (
            channel_packs[0].items[4].type
            == proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT
        )
        assert channel_packs[0].items[4].alt_icon == 0
        assert channel_packs[0].items[4].user_icon == 0
        assert channel_packs[0].items[4].default_config_crc32 == 3093446211

        assert channel_packs[1].items[0].caption == "Measurement 2"
        assert channel_packs[1].items[0].id == 6
        assert channel_packs[1].items[0].device_id == 3
        assert (
            channel_packs[1].items[0].type
            == proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT
        )
        assert channel_packs[1].items[0].alt_icon == 0
        assert channel_packs[1].items[0].user_icon == 0
        assert channel_packs[1].items[0].default_config_crc32 == 2592235365

        assert channel_packs[1].items[1].caption == "Lights 2"
        assert channel_packs[1].items[1].id == 7
        assert channel_packs[1].items[1].device_id == 4
        assert channel_packs[1].items[1].type == proto.ChannelType.RELAY
        assert channel_packs[1].items[1].alt_icon == 0
        assert channel_packs[1].items[1].user_icon == 15666345
        assert channel_packs[1].items[1].default_config_crc32 == 0

        assert channel_packs[1].items[2].caption == "Measurement 3"
        assert channel_packs[1].items[2].id == 8
        assert channel_packs[1].items[2].device_id == 4
        assert (
            channel_packs[1].items[2].type
            == proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT
        )
        assert channel_packs[1].items[2].alt_icon == 0
        assert channel_packs[1].items[2].user_icon == 732673
        assert channel_packs[1].items[2].default_config_crc32 == 3093446211

        assert channel_packs[1].items[3].caption == "Measurement 4"
        assert channel_packs[1].items[3].id == 9
        assert channel_packs[1].items[3].device_id == 4
        assert (
            channel_packs[1].items[3].type
            == proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT
        )
        assert channel_packs[1].items[3].alt_icon == 0
        assert channel_packs[1].items[3].user_icon == 732673
        assert channel_packs[1].items[3].default_config_crc32 == 3093446211

        # scene update
        if server.state.get_scenes():
            assert len(scene_pack.items) == 3

            assert scene_pack.items[0].id == 1
            assert scene_pack.items[0].location_id == 1
            assert scene_pack.items[0].alt_icon == 0
            assert scene_pack.items[0].user_icon == 0
            assert scene_pack.items[0].caption == "Scene 1"

            assert scene_pack.items[1].id == 2
            assert scene_pack.items[1].location_id == 1
            assert scene_pack.items[1].alt_icon == 3
            assert scene_pack.items[1].user_icon == 0
            assert scene_pack.items[1].caption == "Scene 2"

            assert scene_pack.items[2].id == 3
            assert scene_pack.items[2].location_id == 1
            assert scene_pack.items[2].alt_icon == 0
            assert scene_pack.items[2].user_icon == 732673
            assert scene_pack.items[2].caption == "Scene 3"
        else:
            assert len(scene_pack.items) == 0

    assert re.search(r"client\[[^\]]+\] registered", caplog.text) is not None


@pytest.mark.asyncio
async def test_register_client_events(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_client(server, "test"):
        pass
    await asyncio.sleep(0.5)
    assert "[server-test] CLIENT_CONNECTED 1" in caplog.text
    assert "[server-test] CLIENT_DISCONNECTED 1" in caplog.text


@pytest.mark.asyncio
async def test_registration_never_enabled(server: Server) -> None:
    # Note: suplalite has no registration window; devices and clients come from
    # the static config, so registration is never reported as open
    async with open_connection(server) as stream:
        await stream.send(Packet(proto.Call.DCS_GET_REGISTRATION_ENABLED))
        packet = await stream.recv()
        assert packet.call_id == proto.Call.SDC_GET_REGISTRATION_ENABLED_RESULT
        response, _ = encoding.decode(proto.TSDC_RegistrationEnabled, packet.data)
        assert response.client_timestamp == 0
        assert response.iodevice_timestamp == 0


def register_client_message(name: str) -> proto.TCS_RegisterClient_D:
    return proto.TCS_RegisterClient_D(
        email=client_email,
        password="password123",
        guid=client_guid(name),
        authkey=client_authkey(name),
        name=name,
        soft_ver="1.2.3",
        server_name="localhost",
    )


async def do_register_client_invalid(
    stream: PacketStream,
    call: proto.TCS_RegisterClient_D,
    expected: proto.ResultCode,
) -> None:
    await stream.send(Packet(proto.Call.CS_REGISTER_CLIENT_D, encoding.encode(call)))
    packet = await stream.recv()
    assert packet.call_id == proto.Call.SC_REGISTER_CLIENT_RESULT_D
    result, _ = encoding.decode(proto.TSC_RegisterClientResult_D, packet.data)
    assert result.result_code == expected
    # the counts are only meaningful when the registration succeeded
    assert result.client_id == 0
    assert result.channel_count == 0

    # Check server closes the connection
    with pytest.raises(network.NetworkError):
        await stream.recv()


@pytest.mark.asyncio
async def test_register_client_zero_guid(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_client_message("test")
        call.guid = b"\x00" * 16
        await do_register_client_invalid(stream, call, proto.ResultCode.GUID_ERROR)
    assert "client sent an empty guid" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_client_zero_authkey(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_client_message("test")
        call.authkey = b"\x00" * 16
        await do_register_client_invalid(stream, call, proto.ResultCode.AUTHKEY_ERROR)
    assert "client sent an empty authkey" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_client_unknown_guid(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_client_message("test")
        call.guid = b"\xab" * 16
        await do_register_client_invalid(
            stream, call, proto.ResultCode.REGISTRATION_DISABLED
        )

    # the rejection tells the operator how to allow the client
    assert "client not allowed to register; to allow it, configure" in caplog.text
    assert "add_client_credentials(" in caplog.text
    assert repr(client_email) in caplog.text
    assert to_hex(b"\xab" * 16) in caplog.text
    assert to_hex(client_authkey("test")) in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_client_wrong_email(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_client_message("test")
        call.email = "wrong@example.com"
        await do_register_client_invalid(stream, call, proto.ResultCode.BAD_CREDENTIALS)
    assert "client not allowed to register" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_client_wrong_authkey(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_client_message("test")
        call.authkey = b"\xff" * 16
        await do_register_client_invalid(stream, call, proto.ResultCode.BAD_CREDENTIALS)
    assert "client not allowed to register" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_client_email_is_case_insensitive(server: Server) -> None:
    async with open_connection(server) as stream:
        call = register_client_message("test")
        call.email = client_email.upper()
        await stream.send(
            Packet(proto.Call.CS_REGISTER_CLIENT_D, encoding.encode(call))
        )
        packet = await stream.recv()
        result, _ = encoding.decode(proto.TSC_RegisterClientResult_D, packet.data)
        assert result.result_code == proto.ResultCode.TRUE


@pytest.mark.asyncio
async def test_register_client_without_client_auth() -> None:
    # any client is accepted, and gets an id after the configured ones
    server = make_server(client_auth=False)
    await server.start()
    try:
        async with open_connection(server) as stream:
            call = register_client_message("test")
            call.email = "wrong@example.com"
            call.guid = b"\xab" * 16
            call.authkey = b"\x00" * 16
            await stream.send(
                Packet(proto.Call.CS_REGISTER_CLIENT_D, encoding.encode(call))
            )
            packet = await stream.recv()
            result, _ = encoding.decode(proto.TSC_RegisterClientResult_D, packet.data)
            assert result.result_code == proto.ResultCode.TRUE
            assert result.client_id > len(client_names)
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_register_client_without_client_auth_still_checks_guid() -> None:
    server = make_server(client_auth=False)
    await server.start()
    try:
        async with open_connection(server) as stream:
            call = register_client_message("test")
            call.guid = b"\x00" * 16
            await do_register_client_invalid(stream, call, proto.ResultCode.GUID_ERROR)
    finally:
        await server.stop()


def register_client_access_id_message(name: str) -> proto.TCS_RegisterClient_B:
    return proto.TCS_RegisterClient_B(
        access_id=access_id,
        access_id_pwd=access_id_password,
        guid=client_guid(name),
        name=name,
        soft_ver="1.2.3",
        server_name="localhost",
    )


async def do_register_client_access_id_invalid(
    stream: PacketStream,
    call: proto.TCS_RegisterClient_B,
    expected: proto.ResultCode,
) -> None:
    await stream.send(Packet(proto.Call.CS_REGISTER_CLIENT_B, encoding.encode(call)))
    packet = await stream.recv()
    assert packet.call_id == proto.Call.SC_REGISTER_CLIENT_RESULT_D
    result, _ = encoding.decode(proto.TSC_RegisterClientResult_D, packet.data)
    assert result.result_code == expected

    # Check server closes the connection
    with pytest.raises(network.NetworkError):
        await stream.recv()


@pytest.mark.asyncio
async def test_register_client_access_id(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_client_access_id_message("access-id client")
        await stream.send(
            Packet(proto.Call.CS_REGISTER_CLIENT_B, encoding.encode(call))
        )

        # the result comes back as the newest variant, whatever call was used
        packet = await stream.recv()
        assert packet.call_id == proto.Call.SC_REGISTER_CLIENT_RESULT_D
        result, _ = encoding.decode(proto.TSC_RegisterClientResult_D, packet.data)
        assert result.result_code == proto.ResultCode.TRUE
        # this client was not configured, so it is created on registration
        assert result.client_id > len(client_names)
        assert result.channel_count == len(server.state.get_channels())

        # and it is served like any other client
        packet = await stream.recv()
        assert packet.call_id == proto.Call.SC_LOCATIONPACK_UPDATE

    assert "client[access-id client] registered" in caplog.text


@pytest.mark.asyncio
async def test_register_client_access_id_zero_guid(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_client_access_id_message("test")
        call.guid = b"\x00" * 16
        await do_register_client_access_id_invalid(
            stream, call, proto.ResultCode.GUID_ERROR
        )
    assert "client sent an empty guid" in caplog.text


@pytest.mark.asyncio
async def test_register_client_access_id_unknown(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_client_access_id_message("test")
        call.access_id = 7
        await do_register_client_access_id_invalid(
            stream, call, proto.ResultCode.REGISTRATION_DISABLED
        )
    assert "access id 7 is not configured" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_client_access_id_wrong_password(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_client_access_id_message("test")
        call.access_id_pwd = "wrong-password"
        await do_register_client_access_id_invalid(
            stream, call, proto.ResultCode.BAD_CREDENTIALS
        )
    # Note: the rejection does not log the password, though a REQUEST event
    # handler that logs whole messages -- as tests/device_test.py registers --
    # would see it
    assert f"incorrect password for access id {access_id}" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_client_access_id_without_client_auth() -> None:
    server = make_server(client_auth=False)
    await server.start()
    try:
        async with open_connection(server) as stream:
            call = register_client_access_id_message("test")
            call.access_id = 7
            call.access_id_pwd = "wrong-password"
            await stream.send(
                Packet(proto.Call.CS_REGISTER_CLIENT_B, encoding.encode(call))
            )
            packet = await stream.recv()
            result, _ = encoding.decode(proto.TSC_RegisterClientResult_D, packet.data)
            assert result.result_code == proto.ResultCode.TRUE
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_register_client_access_id_then_email(server: Server) -> None:
    # a client created by registering with an access id is not thereby allowed
    # to register in email mode
    name = "access-id client"
    async with open_connection(server) as stream:
        call = register_client_access_id_message(name)
        await stream.send(
            Packet(proto.Call.CS_REGISTER_CLIENT_B, encoding.encode(call))
        )
        packet = await stream.recv()
        result, _ = encoding.decode(proto.TSC_RegisterClientResult_D, packet.data)
        assert result.result_code == proto.ResultCode.TRUE

    async with open_connection(server) as stream:
        await do_register_client_invalid(
            stream,
            register_client_message(name),
            proto.ResultCode.REGISTRATION_DISABLED,
        )


@pytest.mark.asyncio
async def test_register_client_twice_replaces_connection(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as first:
        client_id, *_ = await register_client(first, "test")
        assert server.state.get_client(client_id).online

        async with open_connection(server) as second:
            await register_client(second, "test")

            # the client stays online, now owned by the new connection
            assert server.state.get_client(client_id).online

            # the server terminates the displaced (stale) connection
            with pytest.raises(network.NetworkError):
                await first.recv()

            # the replacement connection is fully functional
            await ping(second)

    assert "client[test] registered" in caplog.text
    assert "client already connected; replacing existing connection" in caplog.text
    assert "error; closing connection" not in caplog.text


def fail_event_handlers_for(
    monkeypatch: pytest.MonkeyPatch,
    event_context: EventContext,
    event_id: EventId | None = None,
) -> None:
    # Make event dispatch raise outside of the per-handler try, as it would if
    # the dispatch code itself failed
    original = Server.get_event_handlers

    def get_event_handlers(
        self: Server, context: EventContext, id_: EventId
    ) -> list[EventHandler]:
        if context is event_context and event_id in (None, id_):
            raise RuntimeError("event dispatch failed")
        return original(self, context, id_)

    monkeypatch.setattr(Server, "get_event_handlers", get_event_handlers)


@pytest.mark.asyncio
async def test_connection_event_failure_closes_connection(
    server: Server, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with open_connection(server) as stream:
        await register_device(stream, 1)
        assert server.state.get_device(1).online

        fail_event_handlers_for(monkeypatch, EventContext.DEVICE)

        # the value change is fanned back out to the device, whose event task
        # then fails; the connection must be closed rather than left serving
        # calls with a dead event task
        await stream.send(
            Packet(
                proto.Call.DS_DEVICE_CHANNEL_VALUE_CHANGED,
                encoding.encode(
                    proto.TDS_DeviceChannelValue(channel_number=0, value=b"12345678")
                ),
            )
        )
        with pytest.raises(network.NetworkError):
            await stream.recv()

    await asyncio.sleep(0.5)
    assert "event task failed; closing connection" in caplog.text
    assert not server.state.get_device(1).online
    assert "[server-test] DEVICE_DISCONNECTED 1" in caplog.text


@pytest.mark.asyncio
async def test_server_event_loop_survives_dispatch_failure(
    server: Server, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    fail_event_handlers_for(monkeypatch, EventContext.SERVER, EventId.DEVICE_CONNECTED)

    async with open_device(server, 1):
        await asyncio.sleep(0.5)
        assert "event dispatch failed" in caplog.text

        # the event loop keeps running; later events are still dispatched
        async with open_client(server, "test"):
            await asyncio.sleep(0.5)
            assert "[server-test] CLIENT_CONNECTED 1" in caplog.text


def time_out_first_wait_for_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    # Make the first of stop()'s waits report that connections are still open.
    # Waiting for a real timeout to expire instead would leave the test racing
    # the connection it wants to still be there when the wait gives up.
    original = Server._wait_for_connections  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    waited = False

    async def wait_for_connections(
        self: Server,
        timeout: float | None,  # noqa: ASYNC109
    ) -> bool:
        nonlocal waited
        if not waited:
            waited = True
            return False
        return await original(self, timeout)

    monkeypatch.setattr(Server, "_wait_for_connections", wait_for_connections)


@pytest.mark.asyncio
async def test_stop_closes_open_connections(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Note: uses its own server as the test stops it itself
    server = make_server()
    await server.start()

    time_out_first_wait_for_connections(monkeypatch)

    async with open_connection(server, secure=False) as stream:
        await register_device(stream, 1)

        # the device is idle but still connected, so stop() has to close it
        # itself rather than wait for it; the second wait is the real one and
        # has to see the connection go away
        await server.stop(timeout=0.5)

    # Note: assert out here rather than straight after stop(); on Python 3.11
    # coverage does not trace the statements that follow it in the same
    # coroutine, which fails the coverage gate even though the test passes
    assert "timed out waiting for connections to close" in caplog.text
    assert "connections still open" not in caplog.text
    assert "timed out waiting for connection handlers" not in caplog.text
    assert not server.state.get_device(1).online


@pytest.mark.asyncio
async def test_stop_continues_if_connections_do_not_close(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # a connection that has not gone by the time the waits give up must not
    # block shutdown forever. A zero timeout gives every wait no time at all,
    # so the shutdown takes the give-up path whatever the connection does --
    # and whether or not asyncio.Server.wait_closed() waits for the connection
    # handlers, which it only does from Python 3.12.1 onwards.
    server = make_server()
    await server.start()

    async with open_connection(server, secure=False) as stream:
        await register_device(stream, 1)

        await server.stop(timeout=0)

    # let the connection, which outlived the server, finish tearing down
    await asyncio.sleep(0.1)

    assert "timed out waiting for connections to close" in caplog.text
    assert "connections still open; shutting down anyway" in caplog.text
    assert "timed out waiting for connection handlers to finish" in caplog.text


@pytest.mark.asyncio
async def test_stop_stops_accepting_connections(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Note: uses its own server as the test stops it itself
    server = make_server()
    await server.start()
    port = server.port

    async with open_connection(server, secure=False) as stream:
        await register_device(stream, 1)

        # the listening sockets are closed before the connections are waited
        # on, so a peer reconnecting during shutdown is refused rather than
        # accepted and left open once the existing connections are closed
        stop = asyncio.create_task(server.stop(timeout=0.5))
        await asyncio.sleep(0.1)
        with pytest.raises(ConnectionRefusedError):
            await asyncio.open_connection("127.0.0.1", port)
        await stop

        assert "connections still open" not in caplog.text


@pytest.mark.asyncio
async def test_close_connection_before_it_serves(server: Server) -> None:
    # a connection closed before it starts serving -- e.g. one still in the
    # TLS handshake when the server is stopped -- has no call task to cancel
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    try:
        connection = ServerConnection(server, reader, writer)
        connection.close()
        assert writer.is_closing()
    finally:
        writer.close()
        await writer.wait_closed()


@pytest.mark.asyncio
async def test_client_get_channel_state(server: Server) -> None:
    async with (
        open_device(server, 1) as device,
        open_client(server, "Test Client") as client,
    ):
        channel_id = 2
        channel_number = 1  # index in the device's channels

        # client calls get_channel_state
        call = proto.TCS_ChannelStateRequest(
            sender_id=client.client_id, channel_id=channel_id
        )
        await client.stream.send(
            Packet(proto.Call.CSD_GET_CHANNEL_STATE, encoding.encode(call))
        )

        # device receives get channel state
        packet = await device.stream.recv()
        assert packet.call_id == proto.Call.CSD_GET_CHANNEL_STATE
        device_request, _ = encoding.decode(proto.TSD_ChannelStateRequest, packet.data)
        assert device_request.sender_id == client.client_id
        assert device_request.channel_number == channel_number

        # device sends channel state result
        device_response = proto.TDS_ChannelState(
            receiver_id=device_request.sender_id,
            channel_number=1,
            fields=proto.ChannelStateField.MAC,
            default_icon_field=0,
            ipv4=0,
            mac=b"\x01\x02\x03\x04\x05\x06",
            battery_level=0,
            battery_powered=False,
            wifi_rssi=0,
            wifi_signal_strength=0,
            bridge_node_online=False,
            bridge_node_signal_strength=0,
            uptime=0,
            connected_uptime=0,
            battery_health=0,
            last_connection_reset_cause=0,
            light_source_lifespan=0,
            light_source_operating_time=0,
        )
        await device.stream.send(
            Packet(
                proto.Call.DSC_CHANNEL_STATE_RESULT,
                encoding.encode(device_response),
            )
        )

        # client receives channel state result
        packet = await client.stream.recv()
        assert packet.call_id == proto.Call.DSC_CHANNEL_STATE_RESULT
        client_response, _ = encoding.decode(proto.TSC_ChannelState, packet.data)
        assert client_response.receiver_id == client.client_id
        assert client_response.channel_id == channel_id
        assert client_response.mac == b"\x01\x02\x03\x04\x05\x06"


@pytest.mark.asyncio
async def test_client_get_channel_state_invalid_channel(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1), open_client(server, "test") as client:
        await client.stream.send(
            Packet(
                proto.Call.CSD_GET_CHANNEL_STATE,
                encoding.encode(
                    proto.TCS_ChannelStateRequest(
                        sender_id=client.client_id, channel_id=42
                    )
                ),
            )
        )
        await asyncio.sleep(0.5)

    assert "client[test] handle call Call.CSD_GET_CHANNEL_STATE" in caplog.text
    assert (
        "client[test] failed to get channel state; channel id 42 does not exist"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_client_get_channel_state_offline_device(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    # device is not connected, so its channels are offline
    async with open_client(server, "test") as client:
        channel = server.state.get_channel(2)
        await client.stream.send(
            Packet(
                proto.Call.CSD_GET_CHANNEL_STATE,
                encoding.encode(
                    proto.TCS_ChannelStateRequest(
                        sender_id=client.client_id, channel_id=2
                    )
                ),
            )
        )
        await asyncio.sleep(0.5)

    assert "client[test] handle call Call.CSD_GET_CHANNEL_STATE" in caplog.text
    assert (
        f"client[test] failed to get channel state; device {channel.device_id}"
        " is offline" in caplog.text
    )


@pytest.mark.asyncio
async def test_channel_state_result_invalid_channel_number(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_client(server, "test") as client, open_device(server, 1) as device:
        await device.stream.send(
            Packet(
                proto.Call.DSC_CHANNEL_STATE_RESULT,
                encoding.encode(
                    proto.TDS_ChannelState(
                        receiver_id=client.client_id,
                        channel_number=42,
                        fields=proto.ChannelStateField.MAC,
                        default_icon_field=0,
                        ipv4=0,
                        mac=b"\x01\x02\x03\x04\x05\x06",
                        battery_level=0,
                        battery_powered=False,
                        wifi_rssi=0,
                        wifi_signal_strength=0,
                        bridge_node_online=False,
                        bridge_node_signal_strength=0,
                        uptime=0,
                        connected_uptime=0,
                        battery_health=0,
                        last_connection_reset_cause=0,
                        light_source_lifespan=0,
                        light_source_operating_time=0,
                    )
                ),
            )
        )
        await asyncio.sleep(0.5)

    assert "device[device-1] handle call Call.DSC_CHANNEL_STATE_RESULT" in caplog.text
    assert (
        "device[device-1] failed channel state result; channel number 42"
        " does not exist" in caplog.text
    )


@pytest.mark.asyncio
async def test_client_get_all_icons(server: Server) -> None:
    url = f"https://{server.host}:{server.api_port}/api/2.2.0/user-icons"
    async with (
        aiohttp.ClientSession() as session,
        session.get(url, ssl=False) as response,
    ):
        assert response.status == 200
        assert response.headers["content-type"] == "application/json"
        assert await response.json() == [
            {"id": 15666345},
            {"id": 732673},
        ]


@pytest.mark.asyncio
async def test_client_get_multiple_channel_icons(server: Server) -> None:
    async with open_device(server, 4):
        url = (
            f"https://{server.host}:{server.api_port}/api/2.2.0/"
            "user-icons?ids=15666345,732673&include=images"
        )
        async with (
            aiohttp.ClientSession() as session,
            session.get(url, ssl=False) as response,
        ):  # pragma: no branch
            assert response.status == 200
            assert response.headers["content-type"] == "application/json"
            assert await response.json() == [
                {
                    "id": 15666345,
                    "images": ["aWNvbjE=", "aWNvbjI="],
                    "imagesDark": ["aWNvbjE=", "aWNvbjI="],
                },
                {
                    "id": 732673,
                    "images": ["aWNvbjM="],
                    "imagesDark": ["aWNvbjM="],
                },
            ]


@pytest.mark.asyncio
async def test_client_get_single_channel_icon(server: Server) -> None:
    async with open_device(server, 4):
        url = (
            f"https://{server.host}:{server.api_port}/api/2.2.0/"
            "user-icons?ids=732673&include=images"
        )
        async with (
            aiohttp.ClientSession() as session,
            session.get(url, ssl=False) as response,
        ):  # pragma: no branch
            assert response.status == 200
            assert response.headers["content-type"] == "application/json"
            assert await response.json() == [
                {
                    "id": 732673,
                    "images": ["aWNvbjM="],
                    "imagesDark": ["aWNvbjM="],
                },
            ]


@pytest.mark.asyncio
async def test_api_not_found(server: Server) -> None:
    async with open_device(server, 4):
        url = f"https://{server.host}:{server.api_port}/api/2.2.0/foo"
        async with (
            aiohttp.ClientSession() as session,
            session.get(url, ssl=False) as response,
        ):  # pragma: no branch
            assert response.status == 404
            assert response.headers["content-type"] == "application/json"
            assert await response.json() == {"message": "Not found"}


@pytest.mark.asyncio
async def test_client_update_on_device_connect(server: Server) -> None:
    async with (
        open_client(server, "Client A") as client_a,
        open_client(server, "Client B") as client_b,
        open_device(server, 1),
    ):  # pragma: no branch

        def check_packet(packet: Packet) -> None:
            assert packet.call_id == proto.Call.SC_CHANNELVALUE_PACK_UPDATE_B
            msg, _ = encoding.decode(proto.TSC_ChannelValuePack_B, packet.data)
            assert msg.total_left == 0
            assert len(msg.items) == 3

            assert not msg.items[0].eol
            assert msg.items[0].id == 1
            assert msg.items[0].online
            assert msg.items[0].value.value == b"\x00\x00\x00\x00\x00\x00\x00\x00"

            assert not msg.items[1].eol
            assert msg.items[1].id == 2
            assert msg.items[1].online
            assert msg.items[1].value.value == b"\x00\x00\x00\x00\x00\x00\x00\x00"

            assert msg.items[2].eol
            assert msg.items[2].id == 3
            assert msg.items[2].online
            assert msg.items[2].value.value == b"\x00\x00\x00\x00\x00\x00\x00\x00"

        check_packet(await client_a.stream.recv())
        check_packet(await client_b.stream.recv())


def _connect_device(server: Server) -> AbstractAsyncContextManager[Connection]:
    return open_device(server, 1)


def _connect_client(server: Server) -> AbstractAsyncContextManager[Connection]:
    return open_client(server, "test")


connectors: dict[str, Any] = {
    "argnames": "connect",
    "argvalues": (_connect_device, _connect_client),
    "ids": ("device", "client"),
}


@pytest.mark.asyncio
@pytest.mark.parametrize(**connectors)
async def test_device_ping(
    server: Server,
    connect: Callable[[Server], AbstractAsyncContextManager[Connection]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with connect(server) as conn:
        now = time.time()
        call = proto.TDCS_PingServer(
            proto.TimeVal(tv_sec=int(now), tv_usec=int((now - int(now)) * 1000000))
        )
        await conn.stream.send(
            Packet(proto.Call.DCS_PING_SERVER, encoding.encode(call))
        )

        packet = await conn.stream.recv()
        assert packet.call_id == proto.Call.SDC_PING_SERVER_RESULT
        encoding.decode(proto.TSDC_PingServerResult, packet.data)
        assert "handle call Call.DCS_PING_SERVER" in caplog.text
        assert "send Call.SDC_PING_SERVER_RESULT" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(**connectors)
async def test_registration_enabled(
    server: Server,
    connect: Callable[[Server], AbstractAsyncContextManager[Connection]],
) -> None:
    async with connect(server) as conn:
        await conn.stream.send(Packet(proto.Call.DCS_GET_REGISTRATION_ENABLED))
        packet = await conn.stream.recv()
        assert packet.call_id == proto.Call.SDC_GET_REGISTRATION_ENABLED_RESULT
        response, _ = encoding.decode(proto.TSDC_RegistrationEnabled, packet.data)
        assert response.client_timestamp == 0
        assert response.iodevice_timestamp == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(**connectors)
async def test_set_activity_timeout(
    server: Server,
    connect: Callable[[Server], AbstractAsyncContextManager[Connection]],
) -> None:
    async with connect(server) as conn:
        await conn.stream.send(
            Packet(
                proto.Call.DCS_SET_ACTIVITY_TIMEOUT,
                encoding.encode(
                    proto.TDCS_SetActivityTimeout(
                        activity_timeout=195,
                    )
                ),
            )
        )
        packet = await conn.stream.recv()
        assert packet.call_id == proto.Call.SDC_SET_ACTIVITY_TIMEOUT_RESULT
        response, _ = encoding.decode(proto.TSDC_SetActivityTimeoutResult, packet.data)
        assert response.activity_timeout == 195
        assert response.min == 30
        assert response.max == 240


@pytest.mark.asyncio
async def test_device_activity_timeout_preserved_across_registration(
    server: Server,
) -> None:
    async with open_connection(server) as stream:
        # negotiate the activity timeout before registering
        await stream.send(
            Packet(
                proto.Call.DCS_SET_ACTIVITY_TIMEOUT,
                encoding.encode(proto.TDCS_SetActivityTimeout(activity_timeout=195)),
            )
        )
        packet = await stream.recv()
        assert packet.call_id == proto.Call.SDC_SET_ACTIVITY_TIMEOUT_RESULT

        await register_device(stream, 1)

        # round-trip a ping so the server has applied the post-registration
        # context swap before we inspect it
        await stream.send(Packet(proto.Call.DCS_PING_SERVER))
        packet = await stream.recv()
        assert packet.call_id == proto.Call.SDC_PING_SERVER_RESULT

        connection = server.state._device_connections[1]  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        assert connection._context.activity_timeout == 195  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_client_activity_timeout_preserved_across_registration(
    server: Server,
) -> None:
    async with open_connection(server) as stream:
        # negotiate the activity timeout before registering
        await stream.send(
            Packet(
                proto.Call.DCS_SET_ACTIVITY_TIMEOUT,
                encoding.encode(proto.TDCS_SetActivityTimeout(activity_timeout=195)),
            )
        )
        packet = await stream.recv()
        assert packet.call_id == proto.Call.SDC_SET_ACTIVITY_TIMEOUT_RESULT

        client_id, *_ = await register_client(stream, "test")

        connection = server.state._client_connections[client_id]  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        assert connection._context.activity_timeout == 195  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_device_value_changed(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1) as device, open_client(server, "test") as client:
        await device.stream.send(
            Packet(
                proto.Call.DS_DEVICE_CHANNEL_VALUE_CHANGED,
                encoding.encode(
                    proto.TDS_DeviceChannelValue(
                        channel_number=0,
                        value=b"12345678",
                    )
                ),
            )
        )
        packet = await client.stream.recv()
        assert packet.call_id == proto.Call.SC_CHANNELVALUE_PACK_UPDATE_B
        msg, _ = encoding.decode(proto.TSC_ChannelValuePack_B, packet.data)
        assert msg == proto.TSC_ChannelValuePack_B(
            total_left=0,
            items=[
                proto.TSC_ChannelValue_B(
                    eol=True,
                    id=1,
                    online=True,
                    value=proto.ChannelValue_B(
                        value=b"12345678",
                        sub_value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
                        sub_value_type=0,
                    ),
                )
            ],
        )

    assert (
        "device[device-1] handle call Call.DS_DEVICE_CHANNEL_VALUE_CHANGED"
        in caplog.text
    )
    assert "client[test] handle event EventId.CHANNEL_VALUE_CHANGED" in caplog.text
    assert "client[test] send Call.SC_CHANNELVALUE_PACK_UPDATE_B" in caplog.text

    assert "[server-test] CHANNEL_VALUE_CHANGED 1 3132333435363738" in caplog.text


async def do_execute_action(
    client: Client,
    device: Device,
    action: proto.TCS_Action,
    expectation: list[tuple[int, bytes]],
) -> None:
    await client.stream.send(
        Packet(proto.Call.CS_EXECUTE_ACTION, encoding.encode(action))
    )

    # client receives result
    packet = await client.stream.recv()
    assert packet.call_id == proto.Call.SC_ACTION_EXECUTION_RESULT
    result, _ = encoding.decode(proto.TSC_ActionExecutionResult, packet.data)
    assert result == proto.TSC_ActionExecutionResult(
        result_code=proto.ResultCode.TRUE,
        action_id=action.action_id,
        subject_id=action.subject_id,
        subject_type=action.subject_type,
    )

    # device receives set value
    for expected_channel_number, expected_value in expectation:
        packet = await device.stream.recv()
        assert packet.call_id == proto.Call.SD_CHANNEL_SET_VALUE
        msg, _ = encoding.decode(proto.TSD_ChannelNewValue, packet.data)
        assert msg == proto.TSD_ChannelNewValue(
            sender_id=0,
            channel_number=expected_channel_number,
            duration_ms=0,
            value=expected_value,
        )


@pytest.mark.asyncio
async def test_client_execute_action_on(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1) as device, open_client(server, "test") as client:
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=3,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(2, b"\x01\x00\x00\x00\x00\x00\x00\x00")],
        )
    assert "client[test] handle call Call.CS_EXECUTE_ACTION" in caplog.text
    assert "client[test] send Call.SC_ACTION_EXECUTION_RESULT" in caplog.text
    assert "device[device-1] handle event EventId.CHANNEL_SET_VALUE" in caplog.text
    assert "device[device-1] send Call.SD_CHANNEL_SET_VALUE" in caplog.text

    assert "[server-test] CHANNEL_SET_VALUE 3 0100000000000000" in caplog.text


@pytest.mark.asyncio
async def test_client_execute_action_off(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1) as device, open_client(server, "test") as client:
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_OFF,
                subject_id=3,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(2, b"\x00\x00\x00\x00\x00\x00\x00\x00")],
        )
    assert "client[test] handle call Call.CS_EXECUTE_ACTION" in caplog.text
    assert "client[test] send Call.SC_ACTION_EXECUTION_RESULT" in caplog.text
    assert "device[device-1] handle event EventId.CHANNEL_SET_VALUE" in caplog.text
    assert "device[device-1] send Call.SD_CHANNEL_SET_VALUE" in caplog.text

    assert "[server-test] CHANNEL_SET_VALUE 3 0000000000000000" in caplog.text


@pytest.mark.asyncio
async def test_client_execute_action_toggle(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1) as device, open_client(server, "test") as client:
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TOGGLE,
                subject_id=3,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(2, b"\x01\x00\x00\x00\x00\x00\x00\x00")],
        )
    assert "client[test] handle call Call.CS_EXECUTE_ACTION" in caplog.text
    assert "client[test] send Call.SC_ACTION_EXECUTION_RESULT" in caplog.text
    assert "device[device-1] handle event EventId.CHANNEL_SET_VALUE" in caplog.text
    assert "device[device-1] send Call.SD_CHANNEL_SET_VALUE" in caplog.text

    assert "[server-test] CHANNEL_SET_VALUE 3 0100000000000000" in caplog.text


@pytest.mark.parametrize(
    "device_and_channel",
    [
        (2, 4, 0, b"\x0a\x00\x00\x00\x00\x00\x00\x00"),
        (5, 16, 6, b"\n\xff\x00\x00\x00\x00\x00\x00"),
        (5, 17, 7, b"\x0a\xff\x00\x00\x00\x00\x00\x00"),
    ],
)
@pytest.mark.asyncio
async def test_client_execute_action_set_rgbw_parameters(
    device_and_channel: tuple[int, int, int, bytes],
    server: Server,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with (
        open_device(server, device_and_channel[0]) as device,
        open_client(server, "test") as client,
    ):
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.SET_RGBW_PARAMETERS,
                subject_id=device_and_channel[1],
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=encoding.encode(
                    proto.TAction_RGBW_Parameters(
                        brightness=10,
                        color_brightness=-1,
                        color=0,
                        color_random=False,
                        on_off=False,
                    )
                ),
            ),
            [(device_and_channel[2], device_and_channel[3])],
        )
    assert "client[test] handle call Call.CS_EXECUTE_ACTION" in caplog.text
    assert "client[test] send Call.SC_ACTION_EXECUTION_RESULT" in caplog.text
    assert (
        f"device[device-{device_and_channel[0]}] handle event EventId.CHANNEL_SET_VALUE"
    ) in caplog.text
    assert (
        f"device[device-{device_and_channel[0]}] send Call.SD_CHANNEL_SET_VALUE"
    ) in caplog.text

    assert (
        "[server-test] CHANNEL_SET_VALUE "
        f"{device_and_channel[1]} {device_and_channel[3].hex()}"
    ) in caplog.text


async def do_execute_action_with_error(
    client: Client, action: proto.TCS_Action
) -> None:
    await client.stream.send(
        Packet(proto.Call.CS_EXECUTE_ACTION, encoding.encode(action))
    )
    packet = await client.stream.recv()
    assert packet.call_id == proto.Call.SC_ACTION_EXECUTION_RESULT
    msg, _ = encoding.decode(proto.TSC_ActionExecutionResult, packet.data)
    assert msg == proto.TSC_ActionExecutionResult(
        result_code=proto.ResultCode.FALSE,
        action_id=action.action_id,
        subject_id=action.subject_id,
        subject_type=action.subject_type,
    )


@pytest.mark.asyncio
async def test_client_execute_action_invalid_subject(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1), open_client(server, "test") as client:
        await do_execute_action_with_error(
            client,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=3,
                subject_type=proto.ActionSubjectType.SCHEDULE,
                param=b"",
            ),
        )
    assert (
        "client[test] failed to execute action; "
        "subject type ActionSubjectType.SCHEDULE not supported" in caplog.text
    )


@pytest.mark.asyncio
async def test_client_execute_action_invalid_channel(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1), open_client(server, "test") as client:
        await do_execute_action_with_error(
            client,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=42,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
        )
    assert (
        "client[test] failed to execute action; channel id 42 does not exist"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_client_execute_action_invalid_relay_action(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1), open_client(server, "test") as client:
        await do_execute_action_with_error(
            client,
            proto.TCS_Action(
                action_id=proto.ActionType.OPEN,
                subject_id=3,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
        )
    assert (
        "client[test] failed to execute action; "
        "relay action ActionType.OPEN not supported" in caplog.text
    )


@pytest.mark.asyncio
async def test_client_execute_action_invalid_dimmer_action(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 2), open_client(server, "test") as client:
        await do_execute_action_with_error(
            client,
            proto.TCS_Action(
                action_id=proto.ActionType.INTERRUPT,
                subject_id=4,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
        )
    assert (
        "client[test] failed to execute action; "
        "dimmer action ActionType.INTERRUPT not supported" in caplog.text
    )


@pytest.mark.asyncio
async def test_client_execute_action_invalid_rgb_dimmer_action(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 5), open_client(server, "test") as client:
        await do_execute_action_with_error(
            client,
            proto.TCS_Action(
                action_id=proto.ActionType.INTERRUPT,
                subject_id=16,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
        )
    assert (
        "client[test] failed to execute action; "
        "rgb dimmer action ActionType.INTERRUPT not supported" in caplog.text
    )


@pytest.mark.asyncio
async def test_client_execute_action_invalid_rgbw_dimmer_action(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 5), open_client(server, "test") as client:
        await do_execute_action_with_error(
            client,
            proto.TCS_Action(
                action_id=proto.ActionType.INTERRUPT,
                subject_id=17,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
        )
    assert (
        "client[test] failed to execute action; "
        "rgbw dimmer action ActionType.INTERRUPT not supported" in caplog.text
    )


@pytest.mark.asyncio
async def test_client_execute_action_unsupported_channel_type(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1), open_client(server, "test") as client:
        await do_execute_action_with_error(
            client,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=2,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
        )
    assert (
        "client[test] failed to execute action; "
        "channel type ChannelType.THERMOMETER not supported" in caplog.text
    )


@pytest.mark.asyncio
async def test_client_execute_scene_action(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1) as device, open_client(server, "test") as client:
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.EXECUTE,
                subject_id=1,
                subject_type=proto.ActionSubjectType.SCENE,
                param=b"",
            ),
            [
                (0, b"\x01\x00\x00\x00\x00\x00\x00\x00"),
                (2, b"\x00\x00\x00\x00\x00\x00\x00\x00"),
            ],
        )

    assert "client[test] handle call Call.CS_EXECUTE_ACTION" in caplog.text
    assert "client[test] send Call.SC_ACTION_EXECUTION_RESULT" in caplog.text
    assert "device[device-1] handle event EventId.CHANNEL_SET_VALUE" in caplog.text
    assert "device[device-1] send Call.SD_CHANNEL_SET_VALUE" in caplog.text

    assert "[server-test] CHANNEL_SET_VALUE 1 0100000000000000" in caplog.text
    assert "[server-test] CHANNEL_SET_VALUE 3 0000000000000000" in caplog.text


@pytest.mark.asyncio
async def test_client_execute_scene_action_with_dimmer_brightness(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 2) as device, open_client(server, "test") as client:
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.EXECUTE,
                subject_id=2,
                subject_type=proto.ActionSubjectType.SCENE,
                param=b"",
            ),
            [
                (0, b"\x0a\x00\x00\x00\x00\x00\x00\x00"),
            ],
        )

    assert "client[test] handle call Call.CS_EXECUTE_ACTION" in caplog.text
    assert "client[test] send Call.SC_ACTION_EXECUTION_RESULT" in caplog.text
    assert "device[device-2] handle event EventId.CHANNEL_SET_VALUE" in caplog.text
    assert "device[device-2] send Call.SD_CHANNEL_SET_VALUE" in caplog.text

    assert "[server-test] CHANNEL_SET_VALUE 4 0a00000000000000" in caplog.text


@pytest.mark.asyncio
async def test_client_execute_scene_action_invalid_scene(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1), open_client(server, "test") as client:
        await do_execute_action_with_error(
            client,
            proto.TCS_Action(
                action_id=proto.ActionType.EXECUTE,
                subject_id=42,
                subject_type=proto.ActionSubjectType.SCENE,
                param=b"",
            ),
        )
    assert (
        "client[test] failed to execute action; scene id 42 does not exist"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_client_execute_scene_action_invalid_action(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1), open_client(server, "test") as client:
        await do_execute_action_with_error(
            client,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=1,
                subject_type=proto.ActionSubjectType.SCENE,
                param=b"",
            ),
        )
    assert (
        "client[test] failed to execute action; ActionType.TURN_ON not implemented"
        in caplog.text
    )


async def do_set_value(
    client: Client,
    device: Device,
    value: proto.TCS_NewValue,
    expected_channel_number: int,
) -> None:
    await client.stream.send(Packet(proto.Call.CS_SET_VALUE, encoding.encode(value)))

    # device receives set value
    packet = await device.stream.recv()
    assert packet.call_id == proto.Call.SD_CHANNEL_SET_VALUE
    msg, _ = encoding.decode(proto.TSD_ChannelNewValue, packet.data)
    assert msg == proto.TSD_ChannelNewValue(
        sender_id=0,
        channel_number=expected_channel_number,
        duration_ms=0,
        value=value.value,
    )


@pytest.mark.asyncio
async def test_client_set_value(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1) as device, open_client(server, "test") as client:
        await do_set_value(
            client,
            device,
            proto.TCS_NewValue(
                value_id=3,
                target=proto.Target.CHANNEL,
                value=b"\x01\x02\x03\x04\x05\x06\x07\x08",
            ),
            2,
        )
    assert "client[test] handle call Call.CS_SET_VALUE" in caplog.text
    assert "device[device-1] handle event EventId.CHANNEL_SET_VALUE" in caplog.text
    assert "device[device-1] send Call.SD_CHANNEL_SET_VALUE" in caplog.text

    assert "[server-test] CHANNEL_SET_VALUE 3 0102030405060708" in caplog.text


async def do_set_value_with_error(
    client: Client,
    value: proto.TCS_NewValue,
) -> None:
    await client.stream.send(Packet(proto.Call.CS_SET_VALUE, encoding.encode(value)))
    # Note: no way to wait for failure to be reported, so just check that the
    # error is logged in a timely manner
    await asyncio.sleep(0.5)


@pytest.mark.asyncio
async def test_client_set_value_invalid_target(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1), open_client(server, "test") as client:
        await do_set_value_with_error(
            client,
            proto.TCS_NewValue(
                value_id=3,
                target=proto.Target.IODEVICE,
                value=b"\x01\x02\x03\x04\x05\x06\x07\x08",
            ),
        )
    assert "client[test] handle call Call.CS_SET_VALUE" in caplog.text
    assert "client[test] failed to set value; target not supported" in caplog.text
    assert "device[device-1] handle event EventId.CHANNEL_SET_VALUE" not in caplog.text
    assert "device[device-1] send Call.SD_CHANNEL_SET_VALUE" not in caplog.text


@pytest.mark.asyncio
async def test_client_set_value_invalid_channel(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1), open_client(server, "test") as client:
        await do_set_value_with_error(
            client,
            proto.TCS_NewValue(
                value_id=42,
                target=proto.Target.CHANNEL,
                value=b"\x01\x02\x03\x04\x05\x06\x07\x08",
            ),
        )
    assert "client[test] handle call Call.CS_SET_VALUE" in caplog.text
    assert (
        "client[test] failed to set value; channel id 42 does not exist" in caplog.text
    )
    assert "device[device-1] handle event EventId.CHANNEL_SET_VALUE" not in caplog.text
    assert "device[device-1] send Call.SD_CHANNEL_SET_VALUE" not in caplog.text


@pytest.mark.asyncio
async def test_client_oauth_token(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_client(server, "test") as client:
        await client.stream.send(Packet(proto.Call.CS_OAUTH_TOKEN_REQUEST))

        packet = await client.stream.recv()
        assert packet.call_id == proto.Call.SC_OAUTH_TOKEN_REQUEST_RESULT
        msg, _ = encoding.decode(proto.TSC_OAuthTokenRequestResult, packet.data)
        assert msg.result_code == proto.OAuthResultCode.SUCCESS
        assert msg.token.expires_in == 300
        token = msg.token.token
        key, _, encoded_url = token.decode().partition(".")
        assert len(key) == 86
        url = base64.b64decode(encoded_url).decode()
        assert url == f"https://{server.host}:{server.api_port}"

    assert "client[test] handle call Call.CS_OAUTH_TOKEN_REQUEST" in caplog.text
    assert "client[test] send Call.SC_OAUTH_TOKEN_REQUEST_RESULT" in caplog.text


@pytest.mark.asyncio
async def test_client_auth_request(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_client(server, "test") as client:
        await client.stream.send(
            Packet(
                proto.Call.CS_SUPERUSER_AUTHORIZATION_REQUEST,
                encoding.encode(
                    proto.TCS_SuperUserAuthorizationRequest(
                        email="email@email.com", password="password123"
                    )
                ),
            )
        )

        packet = await client.stream.recv()
        assert packet.call_id == proto.Call.SC_SUPERUSER_AUTHORIZATION_RESULT
        msg, _ = encoding.decode(proto.TSC_SuperUserAuthorizationResult, packet.data)
        assert msg == proto.TSC_SuperUserAuthorizationResult(
            result=proto.ResultCode.AUTHORIZED
        )
    assert (
        "client[test] handle call Call.CS_SUPERUSER_AUTHORIZATION_REQUEST"
        in caplog.text
    )
    assert "client[test] authorized" in caplog.text
    assert "client[test] send Call.SC_SUPERUSER_AUTHORIZATION_RESULT" in caplog.text


@pytest.mark.asyncio
async def test_client_auth_request_fail(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_client(server, "test") as client:
        await client.stream.send(
            Packet(
                proto.Call.CS_SUPERUSER_AUTHORIZATION_REQUEST,
                encoding.encode(
                    proto.TCS_SuperUserAuthorizationRequest(
                        email="email@email.com", password="wrongpassword"
                    )
                ),
            )
        )

        packet = await client.stream.recv()
        assert packet.call_id == proto.Call.SC_SUPERUSER_AUTHORIZATION_RESULT
        msg, _ = encoding.decode(proto.TSC_SuperUserAuthorizationResult, packet.data)
        assert msg == proto.TSC_SuperUserAuthorizationResult(
            result=proto.ResultCode.UNAUTHORIZED
        )
    assert (
        "client[test] handle call Call.CS_SUPERUSER_AUTHORIZATION_REQUEST"
        in caplog.text
    )
    assert "client[test] unauthorized" in caplog.text
    assert "client[test] send Call.SC_SUPERUSER_AUTHORIZATION_RESULT" in caplog.text


def check_config(
    actual: proto.TChannelConfig_GeneralPurposeMeasurement,
    expected: state.GeneralPurposeMeasurementChannelConfig,
) -> None:
    assert actual.value_divider == expected.value_divider
    assert actual.value_multiplier == expected.value_multiplier
    assert actual.value_added == expected.value_added
    assert actual.value_precision == expected.value_precision
    assert actual.unit_before_value == expected.unit_before_value
    assert actual.unit_after_value == expected.unit_after_value
    assert actual.no_space_before_value == expected.no_space_before_value
    assert actual.no_space_after_value == expected.no_space_after_value
    assert not actual.keep_history
    assert actual.chart_type == proto.GeneralPurposeMeasurementChartType.LINEAR
    assert actual.refresh_interval_ms == 0
    assert actual.default_value_divider == expected.value_divider
    assert actual.default_value_multiplier == expected.value_multiplier
    assert actual.default_value_added == expected.value_added
    assert actual.default_value_precision == expected.value_precision
    assert actual.default_unit_before_value == expected.unit_before_value
    assert actual.default_unit_after_value == expected.unit_after_value


async def do_get_channel_config(
    client: Client,
    channel_id: int,
    expected_config: state.GeneralPurposeMeasurementChannelConfig | None,
) -> None:
    await client.stream.send(
        Packet(
            proto.Call.CS_GET_CHANNEL_CONFIG,
            encoding.encode(
                proto.TCS_GetChannelConfigRequest(
                    channel_id=channel_id,
                    config_type=proto.ConfigType.DEFAULT,
                    flags=proto.ChannelConfigRequestFlag.NONE,
                )
            ),
        )
    )

    packet = await client.stream.recv()
    assert packet.call_id == proto.Call.SC_CHANNEL_CONFIG_UPDATE_OR_RESULT
    msg, _ = encoding.decode(proto.TSC_ChannelConfigUpdateOrResult, packet.data)
    assert (
        msg.result == proto.ConfigResult.TRUE
        if expected_config is not None
        else proto.ConfigResult.FALSE
    )
    assert msg.config.channel_id == channel_id
    if expected_config is not None:
        assert msg.config.func == proto.ChannelFunc.GENERAL_PURPOSE_MEASUREMENT
        assert msg.config.config_type == proto.ConfigType.DEFAULT
        config, _ = encoding.decode(
            proto.TChannelConfig_GeneralPurposeMeasurement, msg.config.config
        )
        check_config(config, expected_config)


@pytest.mark.asyncio
async def test_client_get_channel_config_default(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_client(server, "test") as client:
        await do_get_channel_config(
            client, 5, state.GeneralPurposeMeasurementChannelConfig()
        )
    assert "client[test] handle call Call.CS_GET_CHANNEL_CONFIG" in caplog.text
    assert "client[test] send Call.SC_CHANNEL_CONFIG_UPDATE_OR_RESULT" in caplog.text


@pytest.mark.asyncio
async def test_client_get_channel_config_custom(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_client(server, "test") as client:
        await do_get_channel_config(
            client,
            6,
            state.GeneralPurposeMeasurementChannelConfig(
                value_divider=10,
                value_added=42,
                unit_after_value="%",
                no_space_after_value=True,
            ),
        )
    assert "client[test] handle call Call.CS_GET_CHANNEL_CONFIG" in caplog.text
    assert "client[test] send Call.SC_CHANNEL_CONFIG_UPDATE_OR_RESULT" in caplog.text


@pytest.mark.asyncio
async def test_client_get_channel_config_none(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_client(server, "test") as client:
        await do_get_channel_config(client, 2, None)
    assert "client[test] handle call Call.CS_GET_CHANNEL_CONFIG" in caplog.text
    assert "client[test] send Call.SC_CHANNEL_CONFIG_UPDATE_OR_RESULT" in caplog.text


@pytest.mark.asyncio
async def test_client_get_channel_config_invalid_channel_id(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_client(server, "test") as client:
        await do_get_channel_config(client, 42, None)
    assert "client[test] handle call Call.CS_GET_CHANNEL_CONFIG" in caplog.text
    assert "client[test] send Call.SC_CHANNEL_CONFIG_UPDATE_OR_RESULT" in caplog.text
    assert (
        "client[test] failed to get channel config; channel id 42 does not exist"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_calcfg(server: Server, caplog: pytest.LogCaptureFixture) -> None:
    async with open_device(server, 1) as device, open_client(server, "test") as client:
        # client sends config request
        await client.stream.send(
            Packet(
                proto.Call.CS_DEVICE_CALCFG_REQUEST_B,
                encoding.encode(
                    proto.TCS_DeviceCalCfgRequest_B(
                        channel_id=2,
                        target=0,
                        command=31,
                        datatype=42,
                        data=b"foobar",
                    )
                ),
            )
        )

        # device receives config request
        packet = await device.stream.recv()
        assert packet.call_id == proto.Call.SD_DEVICE_CALCFG_REQUEST
        msg, _ = encoding.decode(proto.TSD_DeviceCalCfgRequest, packet.data)
        assert msg == proto.TSD_DeviceCalCfgRequest(
            sender_id=1,
            channel_number=1,
            command=31,
            super_user_authorized=False,
            datatype=42,
            data=b"foobar",
        )

        # device sends config response
        await device.stream.send(
            Packet(
                proto.Call.DS_DEVICE_CALCFG_RESULT,
                encoding.encode(
                    proto.TDS_DeviceCalCfgResult(
                        receiver_id=1,
                        channel_number=1,
                        command=12,
                        result=23,
                        data=b"barbaz",
                    )
                ),
            )
        )

        # client receives config response
        packet = await client.stream.recv()
        assert packet.call_id == proto.Call.SC_DEVICE_CALCFG_RESULT
        result, _ = encoding.decode(proto.TSC_DeviceCalCfgResult, packet.data)
        assert result == proto.TSC_DeviceCalCfgResult(
            channel_id=2,
            command=12,
            result=23,
            data=b"barbaz",
        )

    assert "client[test] handle call Call.CS_DEVICE_CALCFG_REQUEST_B" in caplog.text
    assert "device[device-1] handle event EventId.DEVICE_CONFIG" in caplog.text
    assert "device[device-1] send Call.SD_DEVICE_CALCFG_REQUEST" in caplog.text
    assert "device[device-1] handle call Call.DS_DEVICE_CALCFG_RESULT" in caplog.text
    assert "client[test] handle event EventId.DEVICE_CONFIG_RESULT" in caplog.text
    assert "client[test] send Call.SC_DEVICE_CALCFG_RESULT" in caplog.text


@pytest.mark.asyncio
async def test_calcfg_invalid_channel(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1), open_client(server, "test") as client:
        # client sends config request
        await client.stream.send(
            Packet(
                proto.Call.CS_DEVICE_CALCFG_REQUEST_B,
                encoding.encode(
                    proto.TCS_DeviceCalCfgRequest_B(
                        channel_id=27,
                        target=0,
                        command=31,
                        datatype=42,
                        data=b"foobar",
                    )
                ),
            )
        )
        await asyncio.sleep(0.5)

    assert "client[test] handle call Call.CS_DEVICE_CALCFG_REQUEST_B" in caplog.text
    assert (
        "client[test] failed calcfg request; channel id 27 does not exist"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_calcfg_result_invalid_client(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1) as device:
        # device sends config response
        await device.stream.send(
            Packet(
                proto.Call.DS_DEVICE_CALCFG_RESULT,
                encoding.encode(
                    proto.TDS_DeviceCalCfgResult(
                        receiver_id=42,
                        channel_number=1,
                        command=12,
                        result=23,
                        data=b"barbaz",
                    )
                ),
            )
        )
        await asyncio.sleep(0.5)

    assert "device[device-1] send Call.SD_REGISTER_DEVICE_RESULT" in caplog.text
    assert "device[device-1] handle call Call.DS_DEVICE_CALCFG_RESULT" in caplog.text
    assert (
        "device[device-1] failed calcfg result; client id 42 does not exist"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_calcfg_result_invalid_channel_number(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_client(server, "test"), open_device(server, 1) as device:
        # device sends config response
        await device.stream.send(
            Packet(
                proto.Call.DS_DEVICE_CALCFG_RESULT,
                encoding.encode(
                    proto.TDS_DeviceCalCfgResult(
                        receiver_id=1,
                        channel_number=42,
                        command=12,
                        result=23,
                        data=b"barbaz",
                    )
                ),
            )
        )
        await asyncio.sleep(0.5)

    assert "device[device-1] handle call Call.DS_DEVICE_CALCFG_RESULT" in caplog.text
    assert (
        "device[device-1] failed calcfg result; channel number 42 does not exist"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_unhandled_call(server: Server, caplog: pytest.LogCaptureFixture) -> None:
    async with open_device(server, 1) as device:
        await device.stream.send(
            Packet(
                proto.Call.SD_REGISTER_DEVICE_RESULT,
                b"",
            )
        )
        await asyncio.sleep(0.5)

    assert "device[device-1] send Call.SD_REGISTER_DEVICE_RESULT" in caplog.text
    assert (
        "device[device-1] Unhandled call Call.SD_REGISTER_DEVICE_RESULT" in caplog.text
    )


@pytest.mark.slow
@pytest.mark.asyncio
async def test_timeout(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:  # pragma: no cover
    async with open_device(server, 1):
        await asyncio.sleep(31)
    assert (
        "device[device-1] timed out after 30 seconds; closing connection" in caplog.text
    )


@pytest.mark.asyncio
async def test_disconnect(server: Server, caplog: pytest.LogCaptureFixture) -> None:
    async with open_device(server, 1):
        pass
    await asyncio.sleep(0.5)

    assert "device[device-1] network error: eof" in caplog.text
    assert "device[device-1] call task stopped" in caplog.text
    assert "device[device-1] disconnected" in caplog.text
    assert "device[device-1] event task stopped" in caplog.text
    assert "device[device-1] closed" in caplog.text


@pytest.mark.asyncio
async def test_get_channel_by_name(server: Server) -> None:
    channel = server.state.get_channel_by_name("thermometer")
    assert channel.id == 2
    assert channel.type == proto.ChannelType.THERMOMETER


@pytest.mark.asyncio
async def test_get_channel_by_name_invalid(server: Server) -> None:
    with pytest.raises(KeyError):
        server.state.get_channel_by_name("doesntexist")


@pytest.mark.asyncio
async def test_dimmer_off_on_preserves_brightness(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 2) as device, open_client(server, "test") as client:
        # set brightness = 50
        await do_set_value(
            client,
            device,
            proto.TCS_NewValue(
                value_id=4,
                target=proto.Target.CHANNEL,
                value=b"\x32\x00\x00\x00\x00\x00\x00\x00",
            ),
            0,
        )

        # turn off
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_OFF,
                subject_id=4,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(0, b"\x00\x00\x00\x00\x00\x00\x00\x00")],
        )

        # turn on
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=4,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(0, b"\x32\x00\x00\x00\x00\x00\x00\x00")],
        )


@pytest.mark.asyncio
async def test_dimmer_initial_on_sets_full_brightness(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 2) as device, open_client(server, "test") as client:
        # turn on
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=4,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(0, b"\x64\x00\x00\x00\x00\x00\x00\x00")],
        )


@pytest.mark.asyncio
async def test_dimmer_already_on_preserves_brightness(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 2) as device, open_client(server, "test") as client:
        # set brightness = 50
        await do_set_value(
            client,
            device,
            proto.TCS_NewValue(
                value_id=4,
                target=proto.Target.CHANNEL,
                value=b"\x32\x00\x00\x00\x00\x00\x00\x00",
            ),
            0,
        )

        # turn on
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=4,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(0, b"\x32\x00\x00\x00\x00\x00\x00\x00")],
        )


@pytest.mark.asyncio
async def test_rgb_dimmer_off_on_preserves_brightness_and_color(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 5) as device, open_client(server, "test") as client:
        # set colorBrightness=50, purple (r=128, g=64, b=192), onOff=False
        await do_set_value(
            client,
            device,
            proto.TCS_NewValue(
                value_id=16,
                target=proto.Target.CHANNEL,
                value=b"\x00\x32\xc0\x40\x80\x00\x00\x00",
            ),
            6,
        )

        # turn off (colorBrightness=0, color unchanged, onOff=True)
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_OFF,
                subject_id=16,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(6, b"\x00\x00\xc0\x40\x80\x01\x00\x00")],
        )

        # turn on (colorBrightness=50, color unchanged, onOff=True)
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=16,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(6, b"\x00\x32\xc0\x40\x80\x01\x00\x00")],
        )


@pytest.mark.asyncio
async def test_rgb_dimmer_initial_on_sets_full_brightness_and_white(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 5) as device, open_client(server, "test") as client:
        # turn on
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=16,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(6, b"\x00\x64\x00\x00\x00\x01\x00\x00")],
        )


@pytest.mark.asyncio
async def test_rgb_dimmer_already_on_preserves_brightness_and_color(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 5) as device, open_client(server, "test") as client:
        # set colorBrightness=50, purple (r=128, g=64, b=192)
        await do_set_value(
            client,
            device,
            proto.TCS_NewValue(
                value_id=16,
                target=proto.Target.CHANNEL,
                value=b"\x00\x32\xc0\x40\x80\x00\x00\x00",
            ),
            6,
        )

        # turn on
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=16,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(6, b"\x00\x32\xc0\x40\x80\x01\x00\x00")],
        )


@pytest.mark.asyncio
async def test_rgbw_dimmer_off_on_preserves_brightness_and_color(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 5) as device, open_client(server, "test") as client:
        # set brightness=20, colorBrightness=50, r=128, g=64, b=192, onOff=False
        await do_set_value(
            client,
            device,
            proto.TCS_NewValue(
                value_id=17,
                target=proto.Target.CHANNEL,
                value=b"\x14\x32\xc0\x40\x80\x00\x00\x00",
            ),
            7,
        )

        # turn off (brightness=0, colorBrightness=0, color unchanged, onOff=True)
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_OFF,
                subject_id=17,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(7, b"\x00\x00\xc0\x40\x80\x01\x00\x00")],
        )

        # turn on (brightness=20, colorBrightness=50, color unchanged, onOff=True)
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=17,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(7, b"\x14\x32\xc0\x40\x80\x01\x00\x00")],
        )


@pytest.mark.asyncio
async def test_rgbw_dimmer_initial_on_sets_full_brightness_and_white(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 5) as device, open_client(server, "test") as client:
        # turn on with no previous value: brightness=100, colorBrightness=100
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=17,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(7, b"\x64\x64\x00\x00\x00\x01\x00\x00")],
        )


@pytest.mark.asyncio
async def test_rgbw_dimmer_already_on_preserves_brightness_and_color(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 5) as device, open_client(server, "test") as client:
        # set brightness=20, colorBrightness=50, purple (r=128, g=64, b=192)
        await do_set_value(
            client,
            device,
            proto.TCS_NewValue(
                value_id=17,
                target=proto.Target.CHANNEL,
                value=b"\x14\x32\xc0\x40\x80\x00\x00\x00",
            ),
            7,
        )

        # turn on
        await do_execute_action(
            client,
            device,
            proto.TCS_Action(
                action_id=proto.ActionType.TURN_ON,
                subject_id=17,
                subject_type=proto.ActionSubjectType.CHANNEL,
                param=b"",
            ),
            [(7, b"\x14\x32\xc0\x40\x80\x01\x00\x00")],
        )
