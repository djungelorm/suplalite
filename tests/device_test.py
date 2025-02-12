import asyncio
from typing import Any

import pytest

from suplalite.device import Device, DeviceError, channels
from suplalite.server import Server
from suplalite.server.context import BaseContext
from suplalite.server.events import EventContext, EventId
from suplalite.server.handlers import event_handler

from .conftest import device_guid  # type: ignore


@event_handler(EventContext.SERVER, EventId.REQUEST)
async def handle_packet_received(
    context: BaseContext, _: Any, call: int, msg: Any
) -> None:
    context.log(f"call {call} {msg}")


@pytest.mark.asyncio
async def test_device(server: Server, caplog: pytest.LogCaptureFixture) -> None:
    asyncio.create_task(server.serve_forever())

    device = Device(
        host="localhost",
        port=server.port,
        secure=False,
        email="email@email.com",
        name="device",
        version="1.0.0",
        authkey=b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x0A\x0B\x0C\x0D\x0E\x0F",
        guid=device_guid[1],
    )
    channel_a = channels.Relay()
    channel_b = channels.Temperature()
    channel_c = channels.Relay()
    device.add(channel_a)
    device.add(channel_b)
    device.add(channel_c)

    assert device.get(0) == channel_a
    assert device.get(1) == channel_b
    assert device.get(2) == channel_c

    await device.start()
    await device.connected.wait()
    await device.stop()

    assert (
        "[suplalite.server] server call Call.DS_REGISTER_DEVICE_E "
        "TDS_RegisterDevice_E("
        "email='email@email.com', "
        "authkey=b'\\x01\\x02\\x03\\x04\\x05\\x06\\x07\\x08"
        "\\t\\x00\\n\\x0b\\x0c\\r\\x0e\\x0f', "
        "guid=b'\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00"
        "\\x00\\x00\\x00\\x00\\x00\\x00\\x00', "
        "name='device', "
        "soft_ver='1.0.0', "
        "server_name='localhost', "
        "flags=<DeviceFlag.NONE: 0>, "
        "manufacturer_id=0, "
        "product_id=0, "
        "channels=["
        "TDS_DeviceChannel_C(number=0, type=<ChannelType.RELAY: 2900>, "
        "action_trigger_caps=<ActionCap.TURN_ON|TURN_OFF|TOGGLE_x1|TOGGLE_x2|TOGGLE_x3|"
        "TOGGLE_x4|TOGGLE_x5: 127>, "
        "default_func=<ChannelFunc.POWERSWITCH: 130>, "
        "flags=<ChannelFlag.CHANNELSTATE: 65536>, "
        "value=b'\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00'), "
        "TDS_DeviceChannel_C(number=1, type=<ChannelType.THERMOMETER: 3034>, "
        "action_trigger_caps=<ActionCap.NONE: 0>, default_func=<ChannelFunc.THERMOMETER: 40>, "
        "flags=<ChannelFlag.CHANNELSTATE: 65536>, value=b'\\x00\\x00\\x00\\x00\\x000q\\xc0'), "
        "TDS_DeviceChannel_C(number=2, type=<ChannelType.RELAY: 2900>, "
        "action_trigger_caps=<ActionCap.TURN_ON|TURN_OFF|TOGGLE_x1|TOGGLE_x2|TOGGLE_x3|"
        "TOGGLE_x4|TOGGLE_x5: 127>, "
        "default_func=<ChannelFunc.POWERSWITCH: 130>, "
        "flags=<ChannelFlag.CHANNELSTATE: 65536>, "
        "value=b'\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00')"
        "])" in caplog.text
    )


@pytest.mark.asyncio
async def test_device_ping(server: Server, caplog: pytest.LogCaptureFixture) -> None:
    asyncio.create_task(server.serve_forever())

    device = Device(
        host="localhost",
        port=server.port,
        secure=False,
        email="email@email.com",
        name="device",
        version="1.0.0",
        authkey=b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x0A\x0B\x0C\x0D\x0E\x0F",
        guid=device_guid[1],
    )
    device.add(channels.Relay())
    device.add(channels.Temperature())
    device.add(channels.Relay())

    await device.start()
    await device.connected.wait()
    device._ping_timeout = 3  # pylint: disable=protected-access
    await asyncio.sleep(4)

    await device.stop()

    assert "[suplalite.device] ping" in caplog.text
    assert "[suplalite.device] pong" in caplog.text
    assert "[suplalite.server] server call Call.DCS_PING_SERVER None" in caplog.text


@pytest.mark.asyncio
async def test_no_channels(server: Server) -> None:
    asyncio.create_task(server.serve_forever())

    device = Device(
        host="localhost",
        port=server.port,
        secure=False,
        email="email@email.com",
        name="device",
        version="1.0.0",
        authkey=b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x0A\x0B\x0C\x0D\x0E\x0F",
        guid=device_guid[1],
    )

    await device.start()
    await asyncio.sleep(0.5)
    with pytest.raises(DeviceError):
        await device.stop()


@pytest.mark.asyncio
async def test_wrong_channels(server: Server, caplog: pytest.LogCaptureFixture) -> None:
    asyncio.create_task(server.serve_forever())

    device = Device(
        host="localhost",
        port=server.port,
        secure=False,
        email="email@email.com",
        name="device",
        version="1.0.0",
        authkey=b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x0A\x0B\x0C\x0D\x0E\x0F",
        guid=device_guid[1],
    )
    device.add(channels.Relay())
    device.add(channels.Relay())
    device.add(channels.Temperature())

    await device.start()
    await asyncio.sleep(0.5)
    with pytest.raises(DeviceError):
        await device.stop()

    assert (
        "incorrect type for channel number 1; "
        "expected ChannelType.THERMOMETER got ChannelType.RELAY" in caplog.text
    )
    assert "Register failed: ResultCode.FALSE" in caplog.text


@pytest.mark.asyncio
async def test_channel_state(server: Server, caplog: pytest.LogCaptureFixture) -> None:
    asyncio.create_task(server.serve_forever())

    device = Device(
        host="localhost",
        port=server.port,
        secure=False,
        email="email@email.com",
        name="device",
        version="1.0.0",
        authkey=b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x0A\x0B\x0C\x0D\x0E\x0F",
        guid=device_guid[1],
    )
    device.add(channels.Relay())
    device.add(channels.Temperature())
    device.add(channels.Relay())

    await device.start()
    await device.connected.wait()

    await server.events.add(EventId.GET_CHANNEL_STATE, (0, 1))
    await asyncio.sleep(1)
    await device.stop()

    assert (
        "[suplalite.server] device[device-1] send Call.CSD_GET_CHANNEL_STATE"
        in caplog.text
    )
    assert "[suplalite.device] channel state request" in caplog.text
    assert "[suplalite.device] channel state result" in caplog.text
    assert (
        "[suplalite.server] device[device-1] handle call Call.DSC_CHANNEL_STATE_RESULT"
        in caplog.text
    )
    assert (
        "[suplalite.server] server call "
        "Call.DSC_CHANNEL_STATE_RESULT TDS_ChannelState(receiver_id=0, channel_number=0"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_channel_set_value(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    asyncio.create_task(server.serve_forever())

    device = Device(
        host="localhost",
        port=server.port,
        secure=False,
        email="email@email.com",
        name="device",
        version="1.0.0",
        authkey=b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x0A\x0B\x0C\x0D\x0E\x0F",
        guid=device_guid[1],
    )
    channel = channels.Temperature()
    device.add(channels.Relay())
    device.add(channel)
    device.add(channels.Relay())

    await device.start()
    await device.connected.wait()

    await channel.set_value(42)
    await asyncio.sleep(1)

    assert channel.value == 42

    await device.stop()
    assert "[suplalite.device] channel 1 value changed" in caplog.text
    assert (
        "[suplalite.server] device[device-1] "
        "handle call Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C" in caplog.text
    )
    assert (
        "[suplalite.server] server call Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C "
        "TDS_DeviceChannelValue_C(channel_number=1, offline=False, validity_time_sec=0, "
        "value=b'\\x00\\x00\\x00\\x00\\x00\\x00E@')" in caplog.text
    )


@pytest.mark.asyncio
async def test_server_set_value(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    asyncio.create_task(server.serve_forever())

    device = Device(
        host="localhost",
        port=server.port,
        secure=False,
        email="email@email.com",
        name="device",
        version="1.0.0",
        authkey=b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x0A\x0B\x0C\x0D\x0E\x0F",
        guid=device_guid[1],
    )
    channel = channels.Relay()
    device.add(channel)
    device.add(channels.Temperature())
    device.add(channels.Relay())

    await device.start()
    await device.connected.wait()

    await server.events.add(
        EventId.CHANNEL_SET_VALUE, (1, b"\x01\x00\x00\x00\x00\x00\x00\x00")
    )
    await asyncio.sleep(1)

    assert channel.value

    await device.stop()
    assert "[suplalite.device] channel 0 new value" in caplog.text
    assert "[suplalite.device] channel 0 value changed" in caplog.text
    assert (
        "[suplalite.server] device[device-1] "
        "handle call Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C" in caplog.text
    )
    assert (
        "[suplalite.server] server call Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C "
        "TDS_DeviceChannelValue_C(channel_number=0, offline=False, validity_time_sec=0, "
        "value=b'\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00')" in caplog.text
    )
    assert (
        "[suplalite.server] server call Call.DS_CHANNEL_SET_VALUE_RESULT "
        "TDS_ChannelNewValueResult(channel_number=0, sender_id=0, success=True)"
        in caplog.text
    )


@pytest.mark.parametrize("channel_number", (0, 1, 2, 3, 4))
@pytest.mark.asyncio
async def test_channels(
    server: Server, caplog: pytest.LogCaptureFixture, channel_number: int
) -> None:
    asyncio.create_task(server.serve_forever())

    device = Device(
        host="localhost",
        port=server.port,
        secure=False,
        email="email@email.com",
        name="device",
        version="1.0.0",
        authkey=b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x0A\x0B\x0C\x0D\x0E\x0F",
        guid=device_guid[5],
    )

    values = []

    async def on_change(channel: channels.Relay, value: bool) -> None:
        values.append(value)
        await channel.do_set_value(value)

    relay = channels.Relay(on_change=on_change)
    temp = channels.Temperature()
    humi = channels.Humidity()
    tempandhumi = channels.TemperatureAndHumidity()
    gpm = channels.GeneralPurposeMeasurement()
    device.add(relay)
    device.add(temp)
    device.add(humi)
    device.add(tempandhumi)
    device.add(gpm)

    await device.start()
    await device.connected.wait()

    if channel_number == 0:
        await relay.set_value(True)
        await relay.set_value(False)
        assert values == [True, False]

    if channel_number == 1:
        await temp.set_value(3.14)

    if channel_number == 2:
        await humi.set_value(42)

    if channel_number == 3:
        await tempandhumi.set_temperature(42)
        await tempandhumi.set_humidity(3.14)

    if channel_number == 4:
        await gpm.set_value(1.234)

    await asyncio.sleep(0.5)
    await device.stop()

    assert f"[suplalite.device] channel {channel_number} value changed" in caplog.text
    assert (
        "device[device-5] handle call Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C"
        in caplog.text
    )

    if channel_number == 0:
        assert (
            "[suplalite.server] server call Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C "
            "TDS_DeviceChannelValue_C(channel_number=0, offline=False, validity_time_sec=0, "
            "value=b'\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00')" in caplog.text
        )
        assert (
            "[suplalite.server] server call Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C "
            "TDS_DeviceChannelValue_C(channel_number=0, offline=False, validity_time_sec=0, "
            "value=b'\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00')" in caplog.text
        )

    if channel_number == 1:
        assert (
            "[suplalite.server] server call Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C "
            "TDS_DeviceChannelValue_C(channel_number=1, offline=False, validity_time_sec=0, "
            "value=b'\\x1f\\x85\\xebQ\\xb8\\x1e\\t@')" in caplog.text
        )

    if channel_number == 2:
        assert (
            "[suplalite.server] server call Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C "
            "TDS_DeviceChannelValue_C(channel_number=2, offline=False, validity_time_sec=0, "
            "value=b'\\xc8\\xcd\\xfb\\xff\\x10\\xa4\\x00\\x00')" in caplog.text
        )

    if channel_number == 3:
        assert (
            "[suplalite.server] server call Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C "
            "TDS_DeviceChannelValue_C(channel_number=3, offline=False, validity_time_sec=0, "
            "value=b'\\x10\\xa4\\x00\\x00\\x18\\xfc\\xff\\xff')" in caplog.text
        )
        assert (
            "[suplalite.server] server call Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C "
            "TDS_DeviceChannelValue_C(channel_number=3, offline=False, validity_time_sec=0, "
            "value=b'\\x10\\xa4\\x00\\x00D\\x0c\\x00\\x00')" in caplog.text
        )

    if channel_number == 4:
        assert (
            "[suplalite.server] server call Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C "
            "TDS_DeviceChannelValue_C(channel_number=4, offline=False, validity_time_sec=0, "
            "value=b'X9\\xb4\\xc8v\\xbe\\xf3?')" in caplog.text
        )


@pytest.mark.asyncio
async def test_relay() -> None:
    channel = channels.Relay()
    assert not channel.value
    assert channel.encoded_value == b"\x00\x00\x00\x00\x00\x00\x00\x00"

    await channel.set_value(True)
    assert channel.value
    assert channel.encoded_value == b"\x01\x00\x00\x00\x00\x00\x00\x00"

    await channel.set_encoded_value(b"\x00\x00\x00\x00\x00\x00\x00\x00")
    assert not channel.value

    await channel.set_encoded_value(b"\x01\x00\x00\x00\x00\x00\x00\x00")
    assert channel.value


@pytest.mark.asyncio
async def test_temperature() -> None:
    channel = channels.Temperature()
    assert channel.value is None
    assert channel.encoded_value == b"\x00\x00\x00\x00\x000q\xc0"

    await channel.set_value(3.14)
    assert channel.value == 3.14
    assert channel.encoded_value == b"\x1f\x85\xebQ\xb8\x1e\t@"

    await channel.set_encoded_value(b"X9\xb4\xc8v\xbe\xf3?")
    assert channel.value == 1.234

    await channel.set_encoded_value(b"\x00\x00\x00\x00\x000q\xc0")
    assert channel.value is None


@pytest.mark.asyncio
async def test_humidity() -> None:
    channel = channels.Humidity()
    assert channel.value is None
    assert channel.encoded_value == b"\xc8\xcd\xfb\xff\x18\xfc\xff\xff"

    await channel.set_value(42)
    assert channel.value == 42
    assert channel.encoded_value == b"\xc8\xcd\xfb\xff\x10\xa4\x00\x00"

    await channel.set_encoded_value(b"\xc8\xcd\xfb\xffhB\x00\x00")
    assert channel.value == 17

    await channel.set_encoded_value(b"\xc8\xcd\xfb\xff\x18\xfc\xff\xff")
    assert channel.value is None


@pytest.mark.asyncio
async def test_temperature_and_humidity() -> None:
    channel = channels.TemperatureAndHumidity()
    assert channel.temperature is None
    assert channel.humidity is None
    assert channel.encoded_value == b"\xc8\xcd\xfb\xff\x18\xfc\xff\xff"

    await channel.set_temperature(3.14)
    assert channel.temperature == 3.14
    assert channel.humidity is None
    assert channel.encoded_value == b"D\x0c\x00\x00\x18\xfc\xff\xff"

    await channel.set_humidity(42)
    assert channel.temperature == 3.14
    assert channel.humidity == 42
    assert channel.encoded_value == b"D\x0c\x00\x00\x10\xa4\x00\x00"

    await channel.set_encoded_value(b"\xce\x04\x00\x000o\x01\x00")
    assert channel.temperature == 1.23
    assert channel.humidity == 94

    await channel.set_encoded_value(b"\xc8\xcd\xfb\xff\x18\xfc\xff\xff")
    assert channel.temperature is None
    assert channel.humidity is None


@pytest.mark.asyncio
async def test_general_purpose_measurement() -> None:
    channel = channels.GeneralPurposeMeasurement()
    assert channel.value == 0.0
    assert channel.encoded_value == b"\x00\x00\x00\x00\x00\x00\x00\x00"

    await channel.set_value(3.14)
    assert channel.value == 3.14
    assert channel.encoded_value == b"\x1f\x85\xebQ\xb8\x1e\t@"

    await channel.set_encoded_value(b"\xaeG\xe1z\x14\xae\xf3?")
    assert channel.value == 1.23


@pytest.mark.asyncio
async def test_dimmer() -> None:
    assert channels.Dimmer.encode(0) == b"\x00\x00\x00\x00\x00\x00\x00\x00"
    assert channels.Dimmer.encode(42) == b"*\x00\x00\x00\x00\x00\x00\x00"
    assert channels.Dimmer.encode(100) == b"d\x00\x00\x00\x00\x00\x00\x00"

    assert channels.Dimmer.decode(b"\x00\x00\x00\x00\x00\x00\x00\x00") == 0
    assert channels.Dimmer.decode(b"*\x00\x00\x00\x00\x00\x00\x00") == 42
    assert channels.Dimmer.decode(b"d\x00\x00\x00\x00\x00\x00\x00") == 100

    assert channels.Dimmer.decode(b"*\xff\xff\xff\xff\xff\xff\xff") == 42


async def sub_task() -> None:
    while True:
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_task(server: Server) -> None:
    asyncio.create_task(server.serve_forever())

    device = Device(
        host="localhost",
        port=server.port,
        secure=False,
        email="email@email.com",
        name="device",
        version="1.0.0",
        authkey=b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x0A\x0B\x0C\x0D\x0E\x0F",
        guid=device_guid[1],
    )
    device.add(channels.Relay())
    device.add(channels.Temperature())
    device.add(channels.Relay())

    await device.start()
    await device.connected.wait()

    device.add_task(asyncio.create_task(sub_task()))
    await asyncio.sleep(1)

    await device.stop()
