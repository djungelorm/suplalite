import asyncio
import logging
import random
import time
from typing import Any, cast

from suplalite import device, network, proto
from suplalite.device import Device, channels
from suplalite.logging import configure_logging

configure_logging()
logger = logging.getLogger("example-device")


async def handle_change(channel: channels.Channel, value: Any) -> None:
    logger.info("handle change; channel %s = %s", channel.channel_number, str(value))
    ch = cast("Any", channel)
    if ch.value != value:
        await ch.do_set_value(value)


async def update_loop(device: Device) -> None:
    try:
        logger.debug("update loop started")
        while True:
            temp = cast("channels.Temperature", device.get(1))
            await temp.set_value(random.uniform(10, 30))

            humid = cast("channels.Humidity", device.get(2))
            await humid.set_value(random.uniform(50, 80))

            temp_and_humid = cast("channels.TemperatureAndHumidity", device.get(3))
            await temp_and_humid.set_temperature(random.uniform(10, 30))
            await temp_and_humid.set_humidity(random.uniform(50, 80))

            gp = cast("channels.GeneralPurposeMeasurement", device.get(8))
            await gp.set_value(random.uniform(-100, 100))

            await asyncio.sleep(3)
    finally:
        logger.debug("update loop stopped")


async def main() -> None:
    device = Device(
        host="127.0.0.1",
        port=2016,
        secure=True,
        email="email@email.com",
        name="Test Device",
        version="1.0.0",
        authkey=b"\xff\xff\xff\xff\x4a\xd3\xb8\xaa\x36\x66\x21\x6f\x2a\x86\x42\x23",
        guid=b"\xee\xee\xee\xee\xe5\x34\xd1\xa7\x06\xac\x5f\x41\x67\x19\x89\x9e",
    )

    relay = channels.Relay(on_change=handle_change)
    temperature = channels.Temperature()
    humidity = channels.Humidity()
    temperature_and_humidity = channels.TemperatureAndHumidity()
    fan = channels.Relay(on_change=handle_change)
    tv = channels.Relay(on_change=handle_change)
    lights = channels.Relay(func=proto.ChannelFunc.LIGHTSWITCH, on_change=handle_change)
    traffic_light = channels.Relay(
        func=proto.ChannelFunc.LIGHTSWITCH, on_change=handle_change
    )
    car = channels.GeneralPurposeMeasurement()
    rgb_lights = channels.RGBDimmer(on_change=handle_change)
    rgbw_lights = channels.RGBWDimmer(on_change=handle_change)

    device.add(relay)
    device.add(temperature)
    device.add(humidity)
    device.add(temperature_and_humidity)
    device.add(fan)
    device.add(tv)
    device.add(lights)
    device.add(traffic_light)
    device.add(car)
    device.add(rgb_lights)
    device.add(rgbw_lights)

    await device.start()
    device.add_task(asyncio.create_task(update_loop(device)))
    await device.loop_forever()


if __name__ == "__main__":
    try:
        while True:
            try:
                asyncio.run(main())
            except network.NetworkError as exn:
                logger.warning(str(exn))
                time.sleep(3)
            except device.DeviceError as exn:
                logger.warning(str(exn))
                time.sleep(3)
    except KeyboardInterrupt:
        pass
