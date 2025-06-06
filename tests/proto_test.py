from typing import Any

import pytest

from suplalite import encoding, proto


def test_time_val() -> None:
    msg = proto.TimeVal(1, 2)
    assert str(msg) == "TimeVal(tv_sec=1, tv_usec=2)"
    data = encoding.encode(msg)
    assert data == b"\x01\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00"
    msg, size = encoding.decode(proto.TimeVal, data)
    assert size == 16
    assert str(msg) == "TimeVal(tv_sec=1, tv_usec=2)"


def test_register_device_e() -> None:
    msg = proto.TDS_RegisterDevice_E(
        "email@example.com",
        b"\xDD\xDD\xDD\xDD\x4A\xD3\xB8\xAA\x36\x66\x21\x6F\x2A\x86\x42\x23",
        b"\xCC\xCC\xCC\xCC\xE5\x34\xD1\xA7\x06\xAC\x5F\x41\x67\x19\x89\x9E",
        "Test Client",
        "1.2.3",
        "localhost",
        proto.DeviceFlag.NONE,
        42,
        7,
        [
            proto.TDS_DeviceChannel_C(
                1,
                proto.ChannelType.DIMMER,
                proto.ActionCap.NONE,
                proto.ChannelFunc.DIMMER,
                proto.ChannelFlag.RGBW_COMMANDS_SUPPORTED,
                b"\x06\x00\x00\x00\x00\x00\x00\x00",
            )
        ],
    )
    data = encoding.encode(msg)
    print(data)
    assert data == (
        b"email@example.com\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\xdd\xdd\xdd\xddJ\xd3\xb8\xaa6f!o*\x86B#\xcc\xcc\xcc\xcc"
        b"\xe54\xd1\xa7\x06\xac_Ag\x19\x89\x9eTest Client\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x001.2.3\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00localhost\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00*\x00\x07\x00\x01\x01\xa0\x0f\x00"
        b"\x00\x00\x00\x00\x00\xb4\x00\x00\x00\x00\x01\x00\x00\x06\x00\x00"
        b"\x00\x00\x00\x00\x00"
    )

    decoded_msg, size = encoding.decode(proto.TDS_RegisterDevice_E, data)
    assert size == 609
    assert msg == decoded_msg

    assert msg.email == "email@example.com"
    assert (
        msg.authkey
        == b"\xDD\xDD\xDD\xDD\x4A\xD3\xB8\xAA\x36\x66\x21\x6F\x2A\x86\x42\x23"
    )
    assert (
        msg.guid == b"\xCC\xCC\xCC\xCC\xE5\x34\xD1\xA7\x06\xAC\x5F\x41\x67\x19\x89\x9E"
    )
    assert msg.name == "Test Client"

    msg.channels.append(
        proto.TDS_DeviceChannel_C(
            7,
            proto.ChannelType.DIMMER,
            proto.ActionCap.NONE,
            proto.ChannelFunc.DIMMER,
            proto.ChannelFlag.RGBW_COMMANDS_SUPPORTED,
            b"\x0c\x00\x00\x00\x00\x00\x00\x00",
        )
    )

    data = encoding.encode(msg)
    assert data == (
        b"email@example.com\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\xdd\xdd\xdd\xddJ\xd3\xb8\xaa6f!o*\x86B#\xcc\xcc\xcc\xcc"
        b"\xe54\xd1\xa7\x06\xac_Ag\x19\x89\x9eTest Client\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x001.2.3\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00localhost\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00*\x00\x07\x00\x02\x01\xa0\x0f\x00"
        b"\x00\x00\x00\x00\x00\xb4\x00\x00\x00\x00\x01\x00\x00\x06\x00\x00"
        b"\x00\x00\x00\x00\x00\x07\xa0\x0f\x00\x00\x00\x00\x00\x00\xb4\x00"
        b"\x00\x00\x00\x01\x00\x00\x0c\x00\x00\x00\x00\x00\x00\x00"
    )


def test_register_device_result() -> None:
    msg = proto.TSD_RegisterDeviceResult(proto.ResultCode.TRUE, 2, 3, 4)
    assert (
        str(msg) == "TSD_RegisterDeviceResult("
        "result_code=<ResultCode.TRUE: 3>, activity_timeout=2, version=3, version_min=4)"
    )
    data = encoding.encode(msg)
    assert data == b"\x03\x00\x00\x00\x02\x03\x04"
    msg, size = encoding.decode(proto.TSD_RegisterDeviceResult, data)
    assert size == 7
    assert (
        str(msg) == "TSD_RegisterDeviceResult("
        "result_code=<ResultCode.TRUE: 3>, activity_timeout=2, version=3, version_min=4)"
    )


def test_ping_server() -> None:
    msg = proto.TDCS_PingServer(proto.TimeVal(1, 2))
    assert str(msg) == "TDCS_PingServer(now=TimeVal(tv_sec=1, tv_usec=2))"
    data = encoding.encode(msg)
    assert data == b"\x01\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00"
    msg, size = encoding.decode(proto.TDCS_PingServer, data)
    assert size == 16
    assert str(msg) == "TDCS_PingServer(now=TimeVal(tv_sec=1, tv_usec=2))"


def test_location() -> None:
    msg = proto.TSC_Location(False, 1, "Location")
    assert str(msg) == "TSC_Location(eol=False, id=1, caption='Location')"
    data = encoding.encode(msg)
    assert data == b"\x00\x01\x00\x00\x00\t\x00\x00\x00Location\x00"
    msg, size = encoding.decode(proto.TSC_Location, data)
    assert size == 18
    assert str(msg) == "TSC_Location(eol=False, id=1, caption='Location')"


def test_location_pack_empty() -> None:
    msg = proto.TSC_LocationPack(1, [])
    assert str(msg) == "TSC_LocationPack(total_left=1, items=[])"
    data = encoding.encode(msg)
    assert data == b"\x00\x00\x00\x00\x01\x00\x00\x00"
    msg, size = encoding.decode(proto.TSC_LocationPack, data)
    assert size == 8
    assert str(msg) == "TSC_LocationPack(total_left=1, items=[])"


def test_location_pack() -> None:
    msg = proto.TSC_LocationPack(
        1,
        [
            proto.TSC_Location(False, 1, "Location 1"),
            proto.TSC_Location(False, 2, "Location 2"),
            proto.TSC_Location(True, 3, "Location 3"),
        ],
    )
    assert (
        str(msg) == "TSC_LocationPack(total_left=1, items=["
        "TSC_Location(eol=False, id=1, caption='Location 1'), "
        "TSC_Location(eol=False, id=2, caption='Location 2'), "
        "TSC_Location(eol=True, id=3, caption='Location 3')])"
    )
    data = encoding.encode(msg)
    assert data == (
        b"\x03\x00\x00\x00\x01\x00\x00\x00\x00\x01\x00\x00\x00\x0b\x00\x00\x00Locatio"
        b"n 1\x00\x00\x02\x00\x00\x00\x0b\x00\x00\x00Location 2\x00\x01\x03\x00\x00"
        b"\x00\x0b\x00\x00\x00Location 3\x00"
    )
    msg, size = encoding.decode(proto.TSC_LocationPack, data)
    assert size == 68
    assert (
        str(msg) == "TSC_LocationPack(total_left=1, items=["
        "TSC_Location(eol=False, id=1, caption='Location 1'), "
        "TSC_Location(eol=False, id=2, caption='Location 2'), "
        "TSC_Location(eol=True, id=3, caption='Location 3')])"
    )


def test_channel_state() -> None:
    msg = proto.TDS_ChannelState(
        1,
        2,
        proto.ChannelStateField.MAC,
        4,
        5,
        b"\x01\x02\x03\x04\x05\x06",
        6,
        False,
        7,
        8,
        True,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
    )
    assert str(msg) == (
        "TDS_ChannelState(receiver_id=1, channel_number=2, fields=<ChannelStateField.MAC: 2>, "
        "default_icon_field=4, ipv4=5, mac=b'\\x01\\x02\\x03\\x04\\x05\\x06', "
        "battery_level=6, battery_powered=False,"
        " wifi_rssi=7, wifi_signal_strength=8, bridge_node_online=True, "
        "bridge_node_signal_strength=9, uptime=10, connected_uptime=11, battery_health=12, "
        "last_connection_reset_cause=13, light_source_lifespan=14, "
        "light_source_operating_time=15)"
    )
    data = encoding.encode(msg)
    assert data == (
        b"\x01\x00\x00\x00\x02\x00\x00\x00\x02\x00\x00\x00\x04\x00\x00\x00"
        b"\x05\x00\x00\x00\x01\x02\x03\x04\x05\x06\x06\x00\x07\x08\x01\t\n\x00\x00\x00"
        b"\x0b\x00\x00\x00\x0c\r\x0e\x00\x0f\x00\x00\x00\x00\x00"
    )
    msg, size = encoding.decode(proto.TDS_ChannelState, data)
    assert size == 50
    assert str(msg) == (
        "TDS_ChannelState(receiver_id=1, channel_number=2, fields=<ChannelStateField.MAC: 2>, "
        "default_icon_field=4, ipv4=5, mac=b'\\x01\\x02\\x03\\x04\\x05\\x06', "
        "battery_level=6, battery_powered=False,"
        " wifi_rssi=7, wifi_signal_strength=8, bridge_node_online=True, "
        "bridge_node_signal_strength=9, uptime=10, connected_uptime=11, battery_health=12, "
        "last_connection_reset_cause=13, light_source_lifespan=14, "
        "light_source_operating_time=15)"
    )


def test_data_packet() -> None:
    msg = proto.DataPacket(
        19,
        1,
        proto.Call.DCS_PING_SERVER,
        b"\x01\x02\x03\x04",
    )
    data = encoding.encode(msg)
    assert (
        data
        == b"SUPLA\x13\x01\x00\x00\x00(\x00\x00\x00\x04\x00\x00\x00\x01\x02\x03\x04SUPLA"
    )


def test_partial_decode() -> None:
    data = (
        b"SUPLA\x13\x01\x00\x00\x00(\x00\x00\x00\x04\x00\x00\x00\x01\x02\x03\x04SUPLA"
    )
    cls = proto.DataPacket
    assert encoding.partial_decode(cls, data, 0) == ([], 0)
    assert encoding.partial_decode(cls, data, 1) == ([b"SUPLA"], 5)
    assert encoding.partial_decode(cls, data, 2) == ([b"SUPLA", 19], 6)
    assert encoding.partial_decode(cls, data, 3) == ([b"SUPLA", 19, 1], 10)
    assert encoding.partial_decode(cls, data, 4) == (
        [b"SUPLA", 19, 1, proto.Call.DCS_PING_SERVER],
        14,
    )
    assert encoding.partial_decode(cls, data, 5) == (
        [b"SUPLA", 19, 1, proto.Call.DCS_PING_SERVER, 4],
        18,
    )


@pytest.mark.parametrize(
    "typ,args,size",
    [
        (
            proto.TDS_DeviceChannel_C,
            (
                1,
                proto.ChannelType.DIMMER,
                proto.ActionCap.TURN_OFF | proto.ActionCap.TURN_ON,
                proto.ChannelFunc.DIMMER,
                proto.ChannelFlag.NONE,
                b"\x01\x00\x00\x00\x00\x00\x00\x00",
            ),
            25,
        ),
        (
            proto.TDS_RegisterDevice_E,
            (
                "email@example.com",
                b"\xDD\xDD\xDD\xDD\x4A\xD3\xB8\xAA\x36\x66\x21\x6F\x2A\x86\x42\x23",
                b"\xCC\xCC\xCC\xCC\xE5\x34\xD1\xA7\x06\xAC\x5F\x41\x67\x19\x89\x9E",
                "Test Client",
                "1.2.3",
                "localhost",
                proto.DeviceFlag.NONE,
                42,
                7,
                [
                    proto.TDS_DeviceChannel_C(
                        1,
                        proto.ChannelType.DIMMER,
                        proto.ActionCap.TURN_OFF | proto.ActionCap.TURN_ON,
                        proto.ChannelFunc.DIMMER,
                        proto.ChannelFlag.NONE,
                        b"\x06\x00\x00\x00\x00\x00\x00\x00",
                    )
                ],
            ),
            609,
        ),
        (proto.TSD_RegisterDeviceResult, (proto.ResultCode.TRUE, 1, 2, 3), 7),
        (proto.TDCS_PingServer, (proto.TimeVal(1, 2),), 16),
        (proto.TSDC_PingServerResult, (proto.TimeVal(1, 2),), 16),
        (
            proto.TCS_RegisterClient_D,
            (
                "example@email.com",
                "password123",
                b"\xDD\xDD\xDD\xDD\x4A\xD3\xB8\xAA\x36\x66\x21\x6F\x2A\x86\x42\x23",
                b"\xCC\xCC\xCC\xCC\xE5\x34\xD1\xA7\x06\xAC\x5F\x41\x67\x19\x89\x9E",
                "Test Client",
                "1.2.3",
                "localhost",
            ),
            639,
        ),
        (
            proto.TSC_RegisterClientResult_D,
            (proto.ResultCode.TRUE, 1, 2, 3, 4, 5, 6, 7, 8, 9),
            27,
        ),
        (
            proto.TCS_RegisterPnClientToken,
            (
                proto.TCS_ClientAuthorizationDetails(
                    1,
                    "pwd",
                    "email@example.com",
                    b"\xDD\xDD\xDD\xDD\x4A\xD3\xB8\xAA\x36\x66\x21\x6F\x2A\x86\x42\x23",
                    b"\xCC\xCC\xCC\xCC\xE5\x34\xD1\xA7\x06\xAC\x5F\x41\x67\x19\x89\x9E",
                    "localhost",
                ),
                proto.TCS_PnClientToken(
                    1,
                    proto.Platform.ANDROID,
                    3,
                    "profile",
                    4,
                    "foobar",
                ),
            ),
            461,
        ),
        (proto.TSC_RegisterPnClientTokenResult, (proto.ResultCode.TRUE,), 4),
        (
            proto.TSC_LocationPack,
            (
                1,
                [
                    proto.TSC_Location(False, 1, "Location 1"),
                    proto.TSC_Location(False, 2, "Location 2"),
                    proto.TSC_Location(True, 3, "Location 3"),
                ],
            ),
            68,
        ),
        (
            proto.TSC_ChannelPack_E,
            (
                1,
                [
                    proto.TSC_Channel_E(
                        False,
                        1,
                        1,
                        1,
                        proto.ChannelType.DIMMER,
                        proto.ChannelFunc.LIGHTSWITCH,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        19,
                        True,
                        proto.ChannelValue_B(
                            b"\x00\x00\x00\x00\x00\x00\x00\x00",
                            b"\x00\x00\x00\x00\x00\x00\x00\x00",
                            0,
                        ),
                        "Channel 1",
                    ),
                    proto.TSC_Channel_E(
                        True,
                        2,
                        1,
                        1,
                        proto.ChannelType.DIMMER,
                        proto.ChannelFunc.LIGHTSWITCH,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        19,
                        True,
                        proto.ChannelValue_B(
                            b"\x00\x00\x00\x00\x00\x00\x00\x00",
                            b"\x00\x00\x00\x00\x00\x00\x00\x00",
                            0,
                        ),
                        "Channel 2",
                    ),
                ],
            ),
            164,
        ),
        (
            proto.TCS_SuperUserAuthorizationRequest,
            (
                "email@email.com",
                "password",
            ),
            320,
        ),
    ],
)
def test_encode_decode(
    typ: type[encoding.MessageProtocol], args: tuple[Any, ...], size: int
) -> None:
    msg = typ(*args)
    data = encoding.encode(msg)
    decoded_msg, decoded_size = encoding.decode(typ, data)
    assert decoded_size == size
    assert str(decoded_msg) == str(msg)
