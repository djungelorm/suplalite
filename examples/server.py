import asyncio
import logging
import signal
import struct

from suplalite import proto
from suplalite.device import channels
from suplalite.logging import configure_logging
from suplalite.server import Server
from suplalite.server.context import ClientContext, DeviceContext, ServerContext
from suplalite.server.events import EventContext, EventId
from suplalite.server.handlers import event_handler, get_handlers
from suplalite.server.state import (
    GeneralPurposeMeasurementChannelConfig,
    SceneAction,
    SceneChannelState,
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
    channel = context.server.state.get_channel(channel_id)
    device = context.server.state.get_device(channel.device_id)
    topic = f"supla/{channel.name}/{action}"
    if channel.type == proto.ChannelType.THERMOMETER:
        value = channels.Temperature.decode(channel.value)
        print(topic, value)

    elif channel.type == proto.ChannelType.HUMIDITYSENSOR:
        value = channels.Humidity.decode(channel.value)
        print(topic, value)

    elif channel.type == proto.ChannelType.HUMIDITYANDTEMPSENSOR:
        temp, humi = channels.TemperatureAndHumidity.decode(channel.value)
        print(topic, temp, humi)

    elif channel.type == proto.ChannelType.RELAY:
        value = channels.Relay.decode(channel.value)
        print(topic, value)

    elif channel.type == proto.ChannelType.DIMMER:
        value = channels.Dimmer.decode(channel.value)
        print(topic, value)

    elif channel.type == proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT:
        value = channels.GeneralPurposeMeasurement.decode(channel.value)
        print(topic, value)

    else:
        print(topic, "unknown value")


def load_icon(path):
    with open(path, "rb") as file:
        return file.read()


async def main():
    configure_logging()

    server = Server(
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
        "humidity",
        "Humidity",
        proto.ChannelType.HUMIDITYSENSOR,
        proto.ChannelFunc.HUMIDITY,
        proto.ChannelFlag.CHANNELSTATE,
    )

    server.state.add_channel(
        device_id,
        "temperature-and-humidity",
        "Temperature and Humidity",
        proto.ChannelType.HUMIDITYANDTEMPSENSOR,
        proto.ChannelFunc.HUMIDITYANDTEMPERATURE,
        proto.ChannelFlag.CHANNELSTATE,
    )

    server.state.add_channel(
        device_id,
        "fan",
        "Fan",
        proto.ChannelType.RELAY,
        proto.ChannelFunc.POWERSWITCH,
        proto.ChannelFlag.CHANNELSTATE,
        alt_icon=4,
    )

    server.state.add_channel(
        device_id,
        "tv",
        "TV",
        proto.ChannelType.RELAY,
        proto.ChannelFunc.POWERSWITCH,
        proto.ChannelFlag.CHANNELSTATE,
        alt_icon=1,
    )

    server.state.add_channel(
        device_id,
        "non-dimmable-lights",
        "Non-Dimmable Lights",
        proto.ChannelType.RELAY,
        proto.ChannelFunc.LIGHTSWITCH,
        proto.ChannelFlag.CHANNELSTATE,
    )

    server.state.add_channel(
        device_id,
        "traffic-light",
        "Traffic Light",
        proto.ChannelType.RELAY,
        proto.ChannelFunc.LIGHTSWITCH,
        proto.ChannelFlag.CHANNELSTATE,
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
        proto.ChannelFlag.CHANNELSTATE,
        config=GeneralPurposeMeasurementChannelConfig(
            unit_after_value="%",
            value_precision=1,
        ),
        icons=[load_icon("examples/car.png")],
    )

    device_id = server.state.add_device(
        "lounge-lights",
        bytes.fromhex("7c59477b7b3cdf7887fdd9387f1c9e77"),
        manufacturer_id=7,
        product_id=1,
    )
    server.state.add_channel(
        device_id,
        "lounge-lights",
        "Lounge",
        proto.ChannelType.DIMMER,
        proto.ChannelFunc.DIMMER,
        proto.ChannelFlag.CHANNELSTATE,
    )

    scene = server.state.add_scene(
        "all-off",
        "All Off",
        icons=[
            load_icon("examples/red.png"),
        ],
        channels=[
            SceneChannelState("lounge-lights", proto.ActionType.TURN_OFF),
            SceneChannelState("non-dimmable-lights", proto.ActionType.TURN_OFF),
            SceneChannelState("fan", proto.ActionType.TURN_OFF),
            SceneChannelState("tv", proto.ActionType.TURN_OFF),
            SceneChannelState("relay", proto.ActionType.TURN_OFF),
        ],
    )

    await server.start()
    await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
