import hashlib
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from suplalite import encoding, proto
from suplalite.server import Server, state


def make_server(
    with_scenes: bool = True,
    device_auth: bool = True,
    client_auth: bool = True,
    with_authkeys: bool = True,
) -> Server:
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
        device_auth=device_auth,
        client_auth=client_auth,
        # Note: no delay, so failed registrations do not slow the tests
        auth_failure_delay=0,
    )
    setup_server(server, with_scenes=with_scenes, with_authkeys=with_authkeys)
    return server


@pytest_asyncio.fixture(scope="function")
async def server(request: pytest.FixtureRequest) -> AsyncIterator[Server]:
    with_scenes = not hasattr(request, "param") or "without-scenes" not in request.param
    server = make_server(with_scenes=with_scenes)
    await server.start()
    yield server
    await server.stop()


device_guid = {
    1: b"\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    2: b"\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    3: b"\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    4: b"\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    5: b"\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
}

# Note: device 1's authkey is the one tests/device_test.py passes to Device
device_authkey = {
    1: b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x00\x0a\x0b\x0c\x0d\x0e\x0f",
    2: b"\x02" * 16,
    3: b"\x03" * 16,
    4: b"\x04" * 16,
    5: b"\x05" * 16,
}

# Clients registering in email mode; a real client app generates its own guid
# and authkey, so here they are just derived from the client name
client_email = "email@example.com"
client_names = ["test", "Test Client", "Client A", "Client B"]

access_id = 42
access_id_password = "access-id-password"


def client_guid(name: str) -> bytes:
    return hashlib.sha256(name.encode()).digest()[:16]


def client_authkey(name: str) -> bytes:
    return hashlib.sha256(name.encode()).digest()[16:32]


def setup_server(
    server: Server, with_scenes: bool = True, with_authkeys: bool = True
) -> None:
    def authkey(device_id: int) -> bytes | None:
        return device_authkey[device_id] if with_authkeys else None

    for name in client_names:
        server.state.add_client(client_email, client_guid(name), client_authkey(name))
    server.state.add_access_id(access_id, access_id_password)

    device_id = server.state.add_device("device-1", device_guid[1], authkey(1))
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

    device_id = server.state.add_device(
        "device-2", device_guid[2], authkey(2), manufacturer_id=7, product_id=1
    )
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

    device_id = server.state.add_device("device-3", device_guid[3], authkey(3))
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

    device_id = server.state.add_device("device-4", device_guid[4], authkey(4))
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

    device_id = server.state.add_device("device-5", device_guid[5], authkey(5))
    assert device_id == 5
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
        "general-purpose-measurement",
        "General Purpose Measurement",
        proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT,
        proto.ChannelFunc.GENERAL_PURPOSE_MEASUREMENT,
        proto.ChannelFlag.CHANNELSTATE,
    )
    server.state.add_channel(
        device_id,
        "dimmer",
        "Dimmer",
        proto.ChannelType.DIMMER,
        proto.ChannelFunc.DIMMER,
        proto.ChannelFlag.CHANNELSTATE,
    )
    server.state.add_channel(
        device_id,
        "rgb",
        "RGB",
        proto.ChannelType.RGBLEDCONTROLLER,
        proto.ChannelFunc.RGBLIGHTING,
        proto.ChannelFlag.CHANNELSTATE,
    )
    server.state.add_channel(
        device_id,
        "rgbw",
        "RGBW",
        proto.ChannelType.DIMMERANDRGBLED,
        proto.ChannelFunc.DIMMERANDRGBLIGHTING,
        proto.ChannelFlag.CHANNELSTATE,
    )

    if with_scenes:
        server.state.add_scene(
            "scene-1",
            "Scene 1",
            [
                state.SceneChannelState("relay", proto.ActionType.TURN_ON),
                state.SceneChannelState("relay2", proto.ActionType.TURN_OFF),
            ],
        )
        server.state.add_scene(
            "scene-2",
            "Scene 2",
            [
                state.SceneChannelState(
                    "lights",
                    proto.ActionType.SET_RGBW_PARAMETERS,
                    encoding.encode(
                        proto.TAction_RGBW_Parameters(
                            brightness=10,
                            color_brightness=-1,
                            color=0,
                            color_random=False,
                            on_off=False,
                        )
                    ),
                ),
            ],
            alt_icon=3,
        )
        server.state.add_scene("scene-3", "Scene 3", [], icons=[b"icon3"])
