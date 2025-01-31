import asyncio
import logging
import random
import select
import signal
import time

from suplalite import proto
from suplalite.device import channels, create_supla_device

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)


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
            await device.get(7).set_value(random.uniform(-100, 100))
            await asyncio.sleep(3)

    except Exception as exc:
        logging.error(str(exc), exc_info=exc)
        raise
    finally:
        logger.debug("update loop stopped")


async def main():
    device = create_supla_device(
        host="127.0.0.1",
        port=2015,
        secure=False,
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
    gpmeasurement = channels.GeneralPurposeMeasurement()

    device.add(relay)
    device.add(temperature)
    device.add(humidity)
    device.add(temperature_and_humidity)
    device.add(fan)
    device.add(tv)
    device.add(lights)
    device.add(gpmeasurement)

    await device.start()
    device.add_task(asyncio.create_task(update_loop(device)))
    await device.loop_forever()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    task = asyncio.ensure_future(main())
    try:
        shielded_task = asyncio.shield(task)
        loop.add_signal_handler(signal.SIGINT, lambda: shielded_task.cancel())
        loop.add_signal_handler(signal.SIGTERM, lambda: shielded_task.cancel())
        loop.run_until_complete(shielded_task)
    except asyncio.exceptions.CancelledError:
        print("device disconnected")
