import asyncio
import json
import logging
import signal
import struct

from suplalite import proto
from suplalite.server import (
    ClientContext,
    DeviceContext,
    ServerContext,
    create_supla_server,
)
from suplalite.server.events import EventContext, EventId
from suplalite.server.handlers import event_handler, get_handlers
from suplalite.server.state import GeneralPurposeMeasurementChannelConfig

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)


@event_handler(EventContext.SERVER, EventId.CHANNEL_REGISTER_VALUE)
async def channel_register_value(
    context: ServerContext, channel_id: int, value: bytes
) -> None:
    await update(context, "register", channel_id, value)


@event_handler(EventContext.SERVER, EventId.CHANNEL_SET_VALUE)
async def channel_set_value(
    context: ServerContext, channel_id: int, value: bytes
) -> None:
    await update(context, "set", channel_id, value)


@event_handler(EventContext.SERVER, EventId.CHANNEL_VALUE_CHANGED)
async def channel_value_changed(
    context: ServerContext, channel_id: int, value: bytes
) -> None:
    await update(context, "changed", channel_id, value)


async def update(context, action, channel_id, value):
    channel = await context.server.state.get_channel(channel_id)
    device = await context.server.state.get_device(channel.device_id)
    topic = f"supla/{channel.name}/{action}"
    if channel.typ == proto.ChannelType.THERMOMETER:
        value = struct.unpack("<d", channel.value)[0]
        # FIXME: decode unknown values
        print(topic, round(value, 1))

    elif channel.typ == proto.ChannelType.HUMIDITYSENSOR:
        parts = struct.unpack("ii", channel.value)
        value = parts[1] / 1000.0
        # FIXME: decode unknown values
        print(topic, round(value, 1))

    elif channel.typ == proto.ChannelType.HUMIDITYANDTEMPSENSOR:
        parts = struct.unpack("ii", channel.value)
        temp = parts[0] / 1000.0
        humi = parts[1] / 1000.0
        # FIXME: decode unknown values
        print(topic, json.dumps((round(temp, 1), round(humi, 1))))

    elif channel.typ == proto.ChannelType.RELAY:
        value = struct.unpack("Q", channel.value)[0] == 1
        print(topic, value)

    elif channel.typ == proto.ChannelType.DIMMER:
        value = int(channel.value[0])
        print(topic, value)

    elif channel.typ == proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT:
        value = struct.unpack("d", channel.value)[0]
        print(topic, value)

    else:
        print(topic, "unknown value")


def load_icon(path):
    with open(path, "rb") as file:
        return file.read()


async def main():
    server = create_supla_server(
        listen_host="0.0.0.0",
        host="192.168.1.10",
        port=2015,
        secure_port=2016,
        api_port=5000,
        certfile="ssl/server.cert",
        keyfile="ssl/server.key",
        location_name="Test",
        email="email@email.com",
        password="1",
        handlers=get_handlers(),
    )

    device_id = server.state.add_device(
        "test",
        bytes.fromhex("eeeeeeeee534d1a706ac5f416719899e"),
        0,
        0,
    )

    server.state.add_channel(
        device_id,
        "relay",
        "Relay",
        proto.ChannelType.RELAY,
        proto.ChannelFunc.POWERSWITCH,
    )

    server.state.add_channel(
        device_id,
        "thermometer",
        "Thermometer",
        proto.ChannelType.THERMOMETER,
        proto.ChannelFunc.THERMOMETER,
    )

    server.state.add_channel(
        device_id,
        "humidity",
        "Humidity",
        proto.ChannelType.HUMIDITYSENSOR,
        proto.ChannelFunc.HUMIDITY,
    )

    server.state.add_channel(
        device_id,
        "temperature-and-humidity",
        "Temperature and Humidity",
        proto.ChannelType.HUMIDITYANDTEMPSENSOR,
        proto.ChannelFunc.HUMIDITYANDTEMPERATURE,
    )

    server.state.add_channel(
        device_id,
        "fan",
        "Fan",
        proto.ChannelType.RELAY,
        proto.ChannelFunc.POWERSWITCH,
        alt_icon=4,
    )

    server.state.add_channel(
        device_id,
        "tv",
        "TV",
        proto.ChannelType.RELAY,
        proto.ChannelFunc.POWERSWITCH,
        alt_icon=1,
    )

    server.state.add_channel(
        device_id,
        "non-dimmable-lights",
        "Non-Dimmable Lights",
        proto.ChannelType.RELAY,
        proto.ChannelFunc.LIGHTSWITCH,
    )

    server.state.add_channel(
        device_id,
        "traffic-light",
        "Traffic Light",
        proto.ChannelType.RELAY,
        proto.ChannelFunc.LIGHTSWITCH,
        icons=[
            load_icon("examples/red.png"),
            load_icon("examples/green.png"),
        ],
    )

    server.state.add_channel(
        device_id,
        "car-battery",
        "Car Battery",
        proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT,
        proto.ChannelFunc.GENERAL_PURPOSE_MEASUREMENT,
        config=GeneralPurposeMeasurementChannelConfig(
            unit_after_value="%",
            value_precision=1,
        ),
        icons=[load_icon("examples/car.png")],
    )

    device_id = server.state.add_device(
        "lounge-lights",
        bytes.fromhex("56fd454d0cc07f1be04e5c0bfeb207a9"),
        manufacturer_id=7,
        product_id=1,
    )
    server.state.add_channel(
        device_id,
        "lounge-lights",
        "Lounge",
        proto.ChannelType.DIMMER,
        proto.ChannelFunc.DIMMER,
    )

    await server.start()
    await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
