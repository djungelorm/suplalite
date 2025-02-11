import asyncio
import logging
import random
import select
import signal
import time

from suplalite import device, network, proto
from suplalite.device import channels, create_supla_device

from suplalite.logging import configure_logging


def handle_change(channel, value):
    print("handle change", channel, value)


async def update_loop(device):
    try:
        logging.debug("update loop started")

        while True:
            await device.get(1).set_value(random.uniform(10, 30))
            await device.get(2).set_value(random.uniform(50, 80))
            await device.get(3).set_temperature(random.uniform(10, 30))
            await device.get(3).set_humidity(random.uniform(50, 80))
            await device.get(8).set_value(random.uniform(-100, 100))
            await asyncio.sleep(3)

    except Exception as exc:
        logging.error(str(exc), exc_info=exc)
        raise
    finally:
        logging.debug("update loop stopped")


async def main():
    configure_logging()
    device = create_supla_device(
        host="127.0.0.1",
        port=2016,
        secure=True,
        email="email@email.com",
        name="Test Device",
        version="1.0.0",
        authkey=b"\xFF\xFF\xFF\xFF\x4A\xD3\xB8\xAA\x36\x66\x21\x6F\x2A\x86\x42\x23",
        guid=b"\xEE\xEE\xEE\xEE\xE5\x34\xD1\xA7\x06\xAC\x5F\x41\x67\x19\x89\x9E",
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

    device.add(relay)
    device.add(temperature)
    device.add(humidity)
    device.add(temperature_and_humidity)
    device.add(fan)
    device.add(tv)
    device.add(lights)
    device.add(traffic_light)
    device.add(car)

    await device.start()
    device.add_task(asyncio.create_task(update_loop(device)))
    await device.loop_forever()


if __name__ == "__main__":
    try:
        while True:
            try:
                asyncio.run(main())
            except network.NetworkError as exn:
                print(exn)
                time.sleep(3)
            except device.DeviceError as exn:
                print(exn)
                time.sleep(3)
    except KeyboardInterrupt:
        pass
