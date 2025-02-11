import asyncio

import pytest

from suplalite.device import Device, channels
from suplalite.server import Server

from .conftest import device_guid  # type: ignore


@pytest.mark.asyncio
async def test_device(server: Server) -> None:
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
    await device.stop()
