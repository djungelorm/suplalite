# pylint: disable=redefined-outer-name

# type: ignore
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from suplalite import encoding, proto
from suplalite.server import Server, state


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow to run")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


@pytest_asyncio.fixture(scope="function")
async def server(request) -> AsyncIterator[Server]:
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
    )

    with_scenes = not hasattr(request, "param") or "without-scenes" not in request.param
    setup_server(server, with_scenes=with_scenes)
    await server.start()
    server.with_scenes = with_scenes
    yield server
    await server.stop()


device_guid = {
    1: b"\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    2: b"\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    3: b"\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    4: b"\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    5: b"\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
}


def setup_server(server: Server, with_scenes: bool = True) -> None:
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

    device_id = server.state.add_device("device-5", device_guid[5], 0, 0)
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
