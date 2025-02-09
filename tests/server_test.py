# pylint: disable=redefined-outer-name,too-many-statements

import asyncio
import base64
import hashlib
import logging
import os
import re
import ssl
import time
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass

import aiohttp
import pytest
import pytest_asyncio

from suplalite import encoding, network, proto
from suplalite.packets import Packet, PacketStream
from suplalite.server import Server, state
from suplalite.server.context import ServerContext
from suplalite.server.events import EventContext, EventId
from suplalite.server.handlers import event_handler
from suplalite.utils import to_hex

device_guid = {
    1: b"\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    2: b"\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    3: b"\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    4: b"\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
}


@event_handler(EventContext.SERVER, EventId.DEVICE_CONNECTED)
async def device_connected(
    context: ServerContext, device_id: int  # pylint:disable=unused-argument
) -> None:
    logging.info("server event DEVICE_CONNECTED %d", device_id)


@event_handler(EventContext.SERVER, EventId.DEVICE_CONNECTED)
async def device_connected_with_extra(
    context: ServerContext,  # pylint:disable=unused-argument
    device_id: int,
    extra: str | None = None,
) -> None:
    logging.info("server event DEVICE_CONNECTED %d %s", device_id, extra or "none")


@event_handler(EventContext.SERVER, EventId.DEVICE_DISCONNECTED)
async def device_disconnected(
    context: ServerContext, device_id: int  # pylint:disable=unused-argument
) -> None:
    logging.info("server event DEVICE_DISCONNECTED %d", device_id)


@event_handler(EventContext.SERVER, EventId.CHANNEL_REGISTER_VALUE)
async def channel_register_value(
    context: ServerContext,  # pylint:disable=unused-argument
    channel_id: int,
    value: bytes,
) -> None:
    logging.info("server event CHANNEL_REGISTER_VALUE %d %s", channel_id, to_hex(value))


@event_handler(EventContext.SERVER, EventId.CHANNEL_VALUE_CHANGED)
async def channel_value_changed(
    context: ServerContext,  # pylint:disable=unused-argument
    channel_id: int,
    value: bytes,
) -> None:
    logging.info("server event CHANNEL_VALUE_CHANGED %d %s", channel_id, to_hex(value))


@event_handler(EventContext.SERVER, EventId.CHANNEL_SET_VALUE)
async def channel_set_value(
    context: ServerContext,  # pylint:disable=unused-argument
    channel_id: int,
    value: bytes,
) -> None:
    logging.info("server event CHANNEL_SET_VALUE %d %s", channel_id, to_hex(value))


@event_handler(EventContext.SERVER, EventId.CLIENT_CONNECTED)
async def client_connected(
    context: ServerContext, client_id: int  # pylint:disable=unused-argument
) -> None:
    logging.info("server event CLIENT_CONNECTED %d", client_id)


@event_handler(EventContext.SERVER, EventId.CLIENT_DISCONNECTED)
async def client_disconnected(
    context: ServerContext, client_id: int  # pylint:disable=unused-argument
) -> None:
    logging.info("server event CLIENT_DISCONNECTED %d", client_id)


@pytest_asyncio.fixture(scope="function")
async def server() -> AsyncIterator[Server]:
    server = Server(
        listen_host="localhost",
        host="localhost",
        port=0,
        secure_port=0,
        api_port=0,
        certfile="ssl/server.cert",
        keyfile="ssl/server.key",
        location_name="Test",
        email="email@email.com",
        password="password123",
        log_config={},
    )
    setup_server(server)
    await server.start()
    yield server
    await server.stop()


def setup_server(server: Server) -> None:
    device_id = server.state.add_device("device-1", device_guid[1], 0, 0)
    assert device_id == 1
    server.state.add_channel(
        device_id,
        "relay",
        "Relay",
        proto.ChannelType.RELAY,
        proto.ChannelFunc.POWERSWITCH,
        proto.ChannelFlag.CHANNELSTATE,
    )
    server.state.add_channel(
        device_id,
        "thermometer",
        "Thermometer",
        proto.ChannelType.THERMOMETER,
        proto.ChannelFunc.THERMOMETER,
        proto.ChannelFlag.CHANNELSTATE,
    )
    server.state.add_channel(
        device_id,
        "relay2",
        "Relay2",
        proto.ChannelType.RELAY,
        proto.ChannelFunc.POWERSWITCH,
        proto.ChannelFlag.CHANNELSTATE,
    )

    device_id = server.state.add_device("device-2", device_guid[2], 7, 1)
    assert device_id == 2
    server.state.add_channel(
        device_id,
        "lights",
        "Lights",
        proto.ChannelType.DIMMER,
        proto.ChannelFunc.DIMMER,
        proto.ChannelFlag.CHANNELSTATE,
        alt_icon=1,
    )

    device_id = server.state.add_device("device-3", device_guid[3], 0, 0)
    assert device_id == 3
    server.state.add_channel(
        device_id,
        "gpm-1",
        "Measurement 1",
        proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT,
        proto.ChannelFunc.GENERAL_PURPOSE_MEASUREMENT,
        proto.ChannelFlag.CHANNELSTATE,
        config=state.GeneralPurposeMeasurementChannelConfig(),
    )
    server.state.add_channel(
        device_id,
        "gpm-2",
        "Measurement 2",
        proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT,
        proto.ChannelFunc.GENERAL_PURPOSE_MEASUREMENT,
        proto.ChannelFlag.CHANNELSTATE,
        config=state.GeneralPurposeMeasurementChannelConfig(
            value_divider=10,
            value_added=42,
            unit_after_value="%",
            no_space_after_value=True,
        ),
    )

    device_id = server.state.add_device("device-4", device_guid[4], 0, 0)
    assert device_id == 4
    server.state.add_channel(
        device_id,
        "lights-2",
        "Lights 2",
        proto.ChannelType.RELAY,
        proto.ChannelFunc.LIGHTSWITCH,
        proto.ChannelFlag.CHANNELSTATE,
        icons=[b"icon1", b"icon2"],
    )
    server.state.add_channel(
        device_id,
        "gpm-3",
        "Measurement 3",
        proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT,
        proto.ChannelFunc.GENERAL_PURPOSE_MEASUREMENT,
        proto.ChannelFlag.CHANNELSTATE,
        config=state.GeneralPurposeMeasurementChannelConfig(),
        icons=[b"icon3"],
    )
    server.state.add_channel(
        device_id,
        "gpm-4",
        "Measurement 4",
        proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT,
        proto.ChannelFunc.GENERAL_PURPOSE_MEASUREMENT,
        proto.ChannelFlag.CHANNELSTATE,
        config=state.GeneralPurposeMeasurementChannelConfig(),
        icons=[b"icon3"],
    )


@asynccontextmanager
async def open_connection(
    server: Server, secure: bool = True
) -> AsyncIterator[PacketStream]:
    port = server.secure_port if secure else server.port
    ssl_context = None
    if secure:
        ssl_context = ssl.SSLContext()
        ssl_context.check_hostname = False

    reader, writer = await asyncio.open_connection("localhost", port, ssl=ssl_context)
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
) -> AsyncIterator[Device]:
    async with open_connection(server, secure) as device:
        await register_device(device, device_id)
        yield Device(device)


@dataclass
class Client(Connection):
    client_id: int
    location_pack: proto.TSC_LocationPack
    channel_pack: proto.TSC_ChannelPack_D
    scene_pack: proto.TSC_ScenePack


@asynccontextmanager
async def open_client(
    server: Server, name: str, secure: bool = True
) -> AsyncIterator[Client]:
    async with open_connection(server, secure) as stream:
        client_id, location_pack, channel_pack, scene_pack = await register_client(
            stream, name
        )
        yield Client(stream, client_id, location_pack, channel_pack, scene_pack)


def register_device_message(device_id: int) -> proto.TDS_RegisterDevice_E:
    manufacturer_id = 0
    product_id = 0
    channels = []
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
    else:
        raise NotImplementedError  # pragma: no cover

    return proto.TDS_RegisterDevice_E(
        email="email@example.com",
        guid=device_guid[device_id],
        authkey=os.urandom(16),
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


async def register_client(stream: PacketStream, name: str) -> tuple[
    int,
    proto.TSC_LocationPack,
    proto.TSC_ChannelPack_D,
    proto.TSC_ScenePack,
]:
    hsh = hashlib.sha256(name.encode()).digest()
    call = proto.TCS_RegisterClient_D(
        email="email@example.com",
        password="password123",
        guid=hsh[:16],
        authkey=hsh[16:32],
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

    # channel update
    packet = await stream.recv()
    assert packet.call_id == proto.Call.SC_CHANNELPACK_UPDATE_D
    channel_pack, _ = encoding.decode(proto.TSC_ChannelPack_D, packet.data)

    # scene update
    packet = await stream.recv()
    assert packet.call_id == proto.Call.SC_SCENE_PACK_UPDATE
    scene_pack, _ = encoding.decode(proto.TSC_ScenePack, packet.data)

    return client_id, location_pack, channel_pack, scene_pack


@pytest.mark.asyncio
@pytest.mark.parametrize("device_id", (1, 2, 3))
@pytest.mark.parametrize("secure", (True, False))
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
    assert "server event CHANNEL_REGISTER_VALUE 1 0000000000000000" in caplog.text
    assert "server event CHANNEL_REGISTER_VALUE 2 0000000000000000" in caplog.text
    assert "server event CHANNEL_REGISTER_VALUE 3 0000000000000000" in caplog.text
    assert "server event DEVICE_CONNECTED 1" in caplog.text
    assert "server event DEVICE_CONNECTED 1 none" in caplog.text
    assert "server event DEVICE_DISCONNECTED 1" in caplog.text


@pytest.mark.asyncio
async def test_event_with_extra(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    await server.events.add(EventId.DEVICE_CONNECTED, (42, "foo"))
    await asyncio.sleep(0.5)
    assert "server event DEVICE_CONNECTED 42 foo" in caplog.text


async def do_register_device_invalid(
    stream: PacketStream, call: proto.TDS_RegisterDevice_E
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
    assert result.result_code == proto.ResultCode.FALSE

    # Check server closes the connection
    with pytest.raises(network.NetworkError):
        await stream.recv()


@pytest.mark.asyncio
async def test_register_device_invalid_guid(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.guid = b"\xFF" * 16
        await do_register_device_invalid(stream, call)
    assert "device not found with guid ffffffffffffffffffffffffffffffff" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_invalid_manufacturer_id(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.manufacturer_id = 16
        await do_register_device_invalid(stream, call)
    assert "manufacturer id mismatch; expected 0 got 16" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_invalid_product_id(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.product_id = 42
        await do_register_device_invalid(stream, call)
    assert "product id mismatch; expected 0 got 42" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_wrong_number_of_channels(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.channels = call.channels[:1]
        await do_register_device_invalid(stream, call)
    assert "incorrect number of channels; expected 3 got 1" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_invalid_channel_number(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.channels[0].number = 10
        await do_register_device_invalid(stream, call)
    assert "incorrect channel number" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_invalid_channel_type(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server) as stream:
        call = register_device_message(1)
        call.channels[1].type = proto.ChannelType.RELAY
        await do_register_device_invalid(stream, call)
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
        await do_register_device_invalid(stream, call)
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
        await do_register_device_invalid(stream, call)
    assert (
        "incorrect flags for channel number 0; "
        "expected ChannelFlag.CHANNELSTATE got ChannelFlag.ZWAVE_BRIDGE|RS_AUTO_CALIBRATION"
        in caplog.text
    )
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_register_device_twice(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1):
        with pytest.raises(AssertionError):
            async with open_device(server, 1):  # pragma no cover
                pass
    assert "device[device-1] registered" in caplog.text
    assert "device already connected" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("secure", (True, False))
async def test_register_client(
    server: Server, secure: bool, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_connection(server, secure) as client:
        _, location_pack, channel_pack, scene_pack = await register_client(
            client, "Test Client"
        )

        # location update
        assert len(location_pack.items) == 1
        assert location_pack.items[0].id == 1
        assert location_pack.items[0].caption == "Test"

        # channel update
        assert len(channel_pack.items) == 9

        assert channel_pack.items[0].caption == "Relay"
        assert channel_pack.items[0].id == 1
        assert channel_pack.items[0].device_id == 1
        assert channel_pack.items[0].type == proto.ChannelType.RELAY
        assert channel_pack.items[0].alt_icon == 0
        assert channel_pack.items[0].user_icon == 0

        assert channel_pack.items[1].caption == "Thermometer"
        assert channel_pack.items[1].id == 2
        assert channel_pack.items[1].device_id == 1
        assert channel_pack.items[1].type == proto.ChannelType.THERMOMETER
        assert channel_pack.items[1].alt_icon == 0
        assert channel_pack.items[1].user_icon == 0

        assert channel_pack.items[2].caption == "Relay2"
        assert channel_pack.items[2].id == 3
        assert channel_pack.items[2].device_id == 1
        assert channel_pack.items[2].type == proto.ChannelType.RELAY
        assert channel_pack.items[2].alt_icon == 0
        assert channel_pack.items[2].user_icon == 0

        assert channel_pack.items[3].caption == "Lights"
        assert channel_pack.items[3].id == 4
        assert channel_pack.items[3].device_id == 2
        assert channel_pack.items[3].type == proto.ChannelType.DIMMER
        assert channel_pack.items[3].alt_icon == 1
        assert channel_pack.items[3].user_icon == 0

        assert channel_pack.items[4].caption == "Measurement 1"
        assert channel_pack.items[4].id == 5
        assert channel_pack.items[4].device_id == 3
        assert (
            channel_pack.items[4].type == proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT
        )
        assert channel_pack.items[4].alt_icon == 0
        assert channel_pack.items[4].user_icon == 0

        assert channel_pack.items[5].caption == "Measurement 2"
        assert channel_pack.items[5].id == 6
        assert channel_pack.items[5].device_id == 3
        assert (
            channel_pack.items[5].type == proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT
        )
        assert channel_pack.items[5].alt_icon == 0
        assert channel_pack.items[5].user_icon == 0

        assert channel_pack.items[6].caption == "Lights 2"
        assert channel_pack.items[6].id == 7
        assert channel_pack.items[6].device_id == 4
        assert channel_pack.items[6].type == proto.ChannelType.RELAY
        assert channel_pack.items[6].alt_icon == 0
        assert channel_pack.items[6].user_icon == 15666345

        assert channel_pack.items[7].caption == "Measurement 3"
        assert channel_pack.items[7].id == 8
        assert channel_pack.items[7].device_id == 4
        assert (
            channel_pack.items[7].type == proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT
        )
        assert channel_pack.items[7].alt_icon == 0
        assert channel_pack.items[7].user_icon == 732673

        assert channel_pack.items[8].caption == "Measurement 4"
        assert channel_pack.items[8].id == 9
        assert channel_pack.items[8].device_id == 4
        assert (
            channel_pack.items[8].type == proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT
        )
        assert channel_pack.items[8].alt_icon == 0
        assert channel_pack.items[8].user_icon == 732673

        # scene update
        assert len(scene_pack.items) == 0

    assert re.search(r"client\[[^\]]+\] registered", caplog.text) is not None


@pytest.mark.asyncio
async def test_register_client_events(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_client(server, "test"):
        pass
    await asyncio.sleep(0.5)
    assert "server event CLIENT_CONNECTED 1" in caplog.text
    assert "server event CLIENT_DISCONNECTED 1" in caplog.text


@pytest.mark.asyncio
async def test_register_client_twice(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_client(server, "test"):
        with pytest.raises(AssertionError):
            async with open_client(server, "test"):  # pragma no cover
                pass
    assert "client[test] registered" in caplog.text
    assert "client already connected" in caplog.text
    assert "error; closing connection" in caplog.text


@pytest.mark.asyncio
async def test_client_get_channel_state(server: Server) -> None:
    async with open_device(server, 1) as device:
        async with open_client(server, "Test Client") as client:
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
            device_request, _ = encoding.decode(
                proto.TSD_ChannelStateRequest, packet.data
            )
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
async def test_client_get_all_icons(server: Server) -> None:
    url = f"https://{server.host}:{server.api_port}/api/2.2.0/user-icons"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, ssl=False) as response:
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
        async with aiohttp.ClientSession() as session:
            async with session.get(url, ssl=False) as response:
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
        async with aiohttp.ClientSession() as session:
            async with session.get(url, ssl=False) as response:
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
async def test_client_update_on_device_connect(server: Server) -> None:
    async with open_client(server, "Client A") as client_a:
        async with open_client(server, "Client B") as client_b:
            async with open_device(server, 1):

                def check_packet(packet: Packet) -> None:
                    assert packet.call_id == proto.Call.SC_CHANNELVALUE_PACK_UPDATE_B
                    msg, _ = encoding.decode(proto.TSC_ChannelValuePack_B, packet.data)
                    assert msg.total_left == 0
                    assert len(msg.items) == 3

                    assert not msg.items[0].eol
                    assert msg.items[0].id == 1
                    assert msg.items[0].online
                    assert (
                        msg.items[0].value.value == b"\x00\x00\x00\x00\x00\x00\x00\x00"
                    )

                    assert not msg.items[1].eol
                    assert msg.items[1].id == 2
                    assert msg.items[1].online
                    assert (
                        msg.items[1].value.value == b"\x00\x00\x00\x00\x00\x00\x00\x00"
                    )

                    assert msg.items[2].eol
                    assert msg.items[2].id == 3
                    assert msg.items[2].online
                    assert (
                        msg.items[2].value.value == b"\x00\x00\x00\x00\x00\x00\x00\x00"
                    )

                check_packet(await client_a.stream.recv())
                check_packet(await client_b.stream.recv())


connectors = {
    "argnames": "connect",
    "argvalues": (
        lambda x: open_device(x, 1),
        lambda x: open_client(x, "test"),
    ),
    "ids": ("device", "client"),
}


@pytest.mark.asyncio
@pytest.mark.parametrize(**connectors)  # type: ignore
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
@pytest.mark.parametrize(**connectors)  # type: ignore
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
@pytest.mark.parametrize(**connectors)  # type: ignore
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
async def test_device_value_changed(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1) as device:
        async with open_client(server, "test") as client:
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

    assert "server event CHANNEL_VALUE_CHANGED 1 3132333435363738" in caplog.text


async def do_execute_action(
    client: Client,
    device: Device,
    action: proto.TCS_Action,
    expected_channel_number: int,
    expected_value: bytes,
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
    async with open_device(server, 1) as device:
        async with open_client(server, "test") as client:
            await do_execute_action(
                client,
                device,
                proto.TCS_Action(
                    action_id=proto.ActionType.TURN_ON,
                    subject_id=3,
                    subject_type=proto.ActionSubjectType.CHANNEL,
                    param=b"",
                ),
                2,
                b"\x01\x00\x00\x00\x00\x00\x00\x00",
            )
    assert "client[test] handle call Call.CS_EXECUTE_ACTION" in caplog.text
    assert "client[test] send Call.SC_ACTION_EXECUTION_RESULT" in caplog.text
    assert "device[device-1] handle event EventId.CHANNEL_SET_VALUE" in caplog.text
    assert "device[device-1] send Call.SD_CHANNEL_SET_VALUE" in caplog.text

    assert "server event CHANNEL_SET_VALUE 3 0100000000000000" in caplog.text


@pytest.mark.asyncio
async def test_client_execute_action_off(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1) as device:
        async with open_client(server, "test") as client:
            await do_execute_action(
                client,
                device,
                proto.TCS_Action(
                    action_id=proto.ActionType.TURN_OFF,
                    subject_id=3,
                    subject_type=proto.ActionSubjectType.CHANNEL,
                    param=b"",
                ),
                2,
                b"\x00\x00\x00\x00\x00\x00\x00\x00",
            )
    assert "client[test] handle call Call.CS_EXECUTE_ACTION" in caplog.text
    assert "client[test] send Call.SC_ACTION_EXECUTION_RESULT" in caplog.text
    assert "device[device-1] handle event EventId.CHANNEL_SET_VALUE" in caplog.text
    assert "device[device-1] send Call.SD_CHANNEL_SET_VALUE" in caplog.text

    assert "server event CHANNEL_SET_VALUE 3 0000000000000000" in caplog.text


@pytest.mark.asyncio
async def test_client_execute_action_toggle(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1) as device:
        async with open_client(server, "test") as client:
            await do_execute_action(
                client,
                device,
                proto.TCS_Action(
                    action_id=proto.ActionType.TOGGLE,
                    subject_id=3,
                    subject_type=proto.ActionSubjectType.CHANNEL,
                    param=b"",
                ),
                2,
                b"\x01\x00\x00\x00\x00\x00\x00\x00",
            )
    assert "client[test] handle call Call.CS_EXECUTE_ACTION" in caplog.text
    assert "client[test] send Call.SC_ACTION_EXECUTION_RESULT" in caplog.text
    assert "device[device-1] handle event EventId.CHANNEL_SET_VALUE" in caplog.text
    assert "device[device-1] send Call.SD_CHANNEL_SET_VALUE" in caplog.text

    assert "server event CHANNEL_SET_VALUE 3 0100000000000000" in caplog.text


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
    async with open_device(server, 1):
        async with open_client(server, "test") as client:
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
        "client[test] failed to execute action; subject type not supported"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_client_execute_action_invalid_channel(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1):
        async with open_client(server, "test") as client:
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
    async with open_device(server, 1):
        async with open_client(server, "test") as client:
            await do_execute_action_with_error(
                client,
                proto.TCS_Action(
                    action_id=proto.ActionType.OPEN,
                    subject_id=3,
                    subject_type=proto.ActionSubjectType.CHANNEL,
                    param=b"",
                ),
            )
    assert "client[test] failed to execute action; action not supported" in caplog.text


@pytest.mark.asyncio
async def test_client_execute_action_invalid_dimmer_action(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 2):
        async with open_client(server, "test") as client:
            await do_execute_action_with_error(
                client,
                proto.TCS_Action(
                    action_id=proto.ActionType.INTERRUPT,
                    subject_id=4,
                    subject_type=proto.ActionSubjectType.CHANNEL,
                    param=b"",
                ),
            )
    assert "client[test] failed to execute action; action not supported" in caplog.text


@pytest.mark.asyncio
async def test_client_execute_action_unsupported_channel_type(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1):
        async with open_client(server, "test") as client:
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
        "client[test] failed to execute action; channel type not supported"
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
    async with open_device(server, 1) as device:
        async with open_client(server, "test") as client:
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

    assert "server event CHANNEL_SET_VALUE 3 0102030405060708" in caplog.text


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
    async with open_device(server, 1):
        async with open_client(server, "test") as client:
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
    async with open_device(server, 1):
        async with open_client(server, "test") as client:
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
async def test_device_set_value_result(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1) as device:
        async with open_client(server, "test") as client:
            async with server.state.lock:
                server.state.set_channel_value(3, b"\x01\x02\x03\x04\x05\x06\x07\x08")
                channel = server.state.get_channel(3)
                assert channel.value == b"\x01\x02\x03\x04\x05\x06\x07\x08"

            await device.stream.send(
                Packet(
                    proto.Call.DS_CHANNEL_SET_VALUE_RESULT,
                    encoding.encode(
                        proto.TDS_ChannelNewValueResult(
                            channel_number=2,
                            sender_id=1,
                            success=True,
                        )
                    ),
                )
            )

            # client receives set value
            packet = await client.stream.recv()
            assert packet.call_id == proto.Call.SC_CHANNELVALUE_PACK_UPDATE_B
            msg, _ = encoding.decode(proto.TSC_ChannelValuePack_B, packet.data)
            assert msg == proto.TSC_ChannelValuePack_B(
                total_left=0,
                items=[
                    proto.TSC_ChannelValue_B(
                        eol=True,
                        id=3,
                        online=True,
                        value=proto.ChannelValue_B(
                            value=b"\x01\x02\x03\x04\x05\x06\x07\x08",
                            sub_value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
                            sub_value_type=0,
                        ),
                    )
                ],
            )
    assert (
        "device[device-1] handle call Call.DS_CHANNEL_SET_VALUE_RESULT" in caplog.text
    )
    assert "client[test] handle event EventId.CHANNEL_VALUE_CHANGED" in caplog.text
    assert "client[test] send Call.SC_CHANNELVALUE_PACK_UPDATE_B" in caplog.text


@pytest.mark.asyncio
async def test_device_set_value_result_invalid_channel_number(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 1) as device:
        async with open_client(server, "test"):
            await device.stream.send(
                Packet(
                    proto.Call.DS_CHANNEL_SET_VALUE_RESULT,
                    encoding.encode(
                        proto.TDS_ChannelNewValueResult(
                            channel_number=42,
                            sender_id=1,
                            success=True,
                        )
                    ),
                )
            )

            # Note: no way to wait for failure to be reported, so just check that the
            # error is logged in a timely manner
            await asyncio.sleep(0.5)

    assert (
        "device[device-1] handle call Call.DS_CHANNEL_SET_VALUE_RESULT" in caplog.text
    )
    assert (
        "device[device-1] failed to handle set value result; channel number 42 does not exist"
        in caplog.text
    )
    assert "client[test] handle event EventId.CHANNEL_VALUE_CHANGED" not in caplog.text
    assert "client[test] send Call.SC_CHANNELVALUE_PACK_UPDATE_B" not in caplog.text


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
                    flags=0,  # FIXME: should be a IntFlag
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
    async with open_device(server, 1) as device:
        async with open_client(server, "test") as client:
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
    async with open_device(server, 1):
        async with open_client(server, "test") as client:
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
    async with open_client(server, "test"):
        async with open_device(server, 1) as device:
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
    async with open_device(server, 2) as device:
        async with open_client(server, "test") as client:
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
                0,
                b"\x00\x00\x00\x00\x00\x00\x00\x00",
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
                0,
                b"\x32\x00\x00\x00\x00\x00\x00\x00",
            )


@pytest.mark.asyncio
async def test_dimmer_initial_on_sets_full_brightness(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 2) as device:
        async with open_client(server, "test") as client:
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
                0,
                b"\x64\x00\x00\x00\x00\x00\x00\x00",
            )


@pytest.mark.asyncio
async def test_dimmer_already_on_preserves_brightness(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    async with open_device(server, 2) as device:
        async with open_client(server, "test") as client:
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
                0,
                b"\x32\x00\x00\x00\x00\x00\x00\x00",
            )
