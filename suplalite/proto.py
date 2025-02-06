# pylint: disable=invalid-name
from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
from enum import Enum, IntFlag

from suplalite.encoding import (
    c_bytes,
    c_enum,
    c_int8,
    c_int16,
    c_int32,
    c_int64,
    c_packed_array,
    c_string,
    c_uint8,
    c_uint16,
    c_uint32,
    c_uint64,
)

ACTIVITY_TIMEOUT_MIN = 30
ACTIVITY_TIMEOUT_MAX = 240

CHANNELMAXCOUNT = 32

TAG = b"SUPLA"

PROTO_VERSION = 23
PROTO_VERSION_MIN = 1
MAX_DATA_SIZE = 10240
RC_MAX_DEV_COUNT = 50
SOFTVER_MAXSIZE = 21

CAPTION_MAXSIZE = 401

GUID_SIZE = 16
GUID_HEXSIZE = 33
LOCATION_PWD_MAXSIZE = 33
ACCESSID_PWD_MAXSIZE = 33
LOCATION_CAPTION_MAXSIZE = CAPTION_MAXSIZE
LOCATIONPACK_MAXCOUNT = 20
CHANNEL_CAPTION_MAXSIZE = CAPTION_MAXSIZE
CHANNEL_GROUP_CAPTION_MAXSIZE = CAPTION_MAXSIZE
CHANNELPACK_MAXCOUNT = 20
URL_HOST_MAXSIZE = 101
URL_PATH_MAXSIZE = 101
SERVER_NAME_MAXSIZE = 65
EMAIL_MAXSIZE = 256  # ver. >= 7
PASSWORD_MAXSIZE = 64  # ver. >= 10
AUTHKEY_SIZE = 16  # ver. >= 7
AUTHKEY_HEXSIZE = 33  # ver. >= 7
OAUTH_TOKEN_MAXSIZE = 256  # ver. >= 10
CHANNELGROUP_PACK_MAXCOUNT = 20  # ver. >= 9
CHANNELGROUP_CAPTION_MAXSIZE = 401  # ver. >= 9
CHANNELVALUE_PACK_MAXCOUNT = 20  # ver. >= 9
CHANNELEXTENDEDVALUE_PACK_MAXCOUNT = 5  # ver. >= 10
CHANNELEXTENDEDVALUE_PACK_MAXDATASIZE = MAX_DATA_SIZE - 50  # ver. >= 10
CALCFG_DATA_MAXSIZE = 128  # ver. >= 10
TIMEZONE_MAXSIZE = 51  # ver. >= 11
ACTION_PARAM_MAXSIZE = 500  # ver. >= 18

CHANNELGROUP_RELATION_PACK_MAXCOUNT = 100  # ver. >= 9

SCENE_CAPTION_MAXSIZE = CAPTION_MAXSIZE  #  ver. >= 18
SCENE_PACK_MAXCOUNT = 20  #  ver. >= 18
SCENE_STATE_PACK_MAXCOUNT = 20  #  ver. >= 18

DEVICE_NAME_MAXSIZE = 201
CLIENT_NAME_MAXSIZE = 201
SENDER_NAME_MAXSIZE = 201
INITIATOR_NAME_MAXSIZE = SENDER_NAME_MAXSIZE

CHANNELVALUE_SIZE = 8

PN_TITLE_MAXSIZE = 101
PN_BODY_MAXSIZE = 256
PN_PROFILE_NAME_MAXSIZE = 51
PN_CLIENT_TOKEN_MAXSIZE = 256

GENERAL_PURPOSE_UNIT_SIZE = 15


class Call(Enum):
    DCS_GETVERSION = 10
    SDC_GETVERSION_RESULT = 20
    SDC_VERSIONERROR = 30
    DCS_PING_SERVER = 40
    SDC_PING_SERVER_RESULT = 50
    DS_REGISTER_DEVICE = 60
    DS_REGISTER_DEVICE_B = 65  # ver. >= 2
    DS_REGISTER_DEVICE_C = 67  # ver. >= 6
    DS_REGISTER_DEVICE_D = 68  # ver. >= 7
    DS_REGISTER_DEVICE_E = 69  # ver. >= 10
    SD_REGISTER_DEVICE_RESULT = 70
    SD_REGISTER_DEVICE_RESULT_B = 71  # ver. >= 25
    DS_REGISTER_DEVICE_F = 75  # ver. >= 23
    DS_REGISTER_DEVICE_G = 76  # ver. >= 25
    CS_REGISTER_CLIENT = 80
    CS_REGISTER_CLIENT_B = 85  # ver. >= 6
    CS_REGISTER_CLIENT_C = 86  # ver. >= 7
    CS_REGISTER_CLIENT_D = 87  # ver. >= 12
    SC_REGISTER_CLIENT_RESULT = 90
    SC_REGISTER_CLIENT_RESULT_B = 92  # ver. >= 9
    SC_REGISTER_CLIENT_RESULT_C = 94  # ver. >= 17
    SC_REGISTER_CLIENT_RESULT_D = 96  # ver. >= 19
    DS_DEVICE_CHANNEL_VALUE_CHANGED = 100
    DS_DEVICE_CHANNEL_VALUE_CHANGED_B = 102  # ver. >= 12
    DS_DEVICE_CHANNEL_VALUE_CHANGED_C = 103  # ver. >= 12
    DS_DEVICE_CHANNEL_EXTENDEDVALUE_CHANGED = 105  # ver. >= 10
    SD_CHANNEL_SET_VALUE = 110
    SD_CHANNELGROUP_SET_VALUE = 115  # ver. >= 13
    DS_CHANNEL_SET_VALUE_RESULT = 120
    SC_LOCATION_UPDATE = 130
    SC_LOCATIONPACK_UPDATE = 140
    SC_CHANNELPACK_UPDATE = 160
    SC_CHANNEL_VALUE_UPDATE = 170
    SC_CHANNEL_VALUE_UPDATE_B = 171
    CS_GET_NEXT = 180
    SC_EVENT = 190
    CS_CHANNEL_SET_VALUE = 200
    CS_CHANNEL_SET_VALUE_B = 205  #  ver. >= 3
    DCS_SET_ACTIVITY_TIMEOUT = 210  #  ver. >= 2
    SDC_SET_ACTIVITY_TIMEOUT_RESULT = 220  #  ver. >= 2
    DS_GET_FIRMWARE_UPDATE_URL = 300  #  ver. >= 5
    SD_GET_FIRMWARE_UPDATE_URL_RESULT = 310  #  ver. >= 5
    DCS_GET_REGISTRATION_ENABLED = 320  #  ver. >= 7
    SDC_GET_REGISTRATION_ENABLED_RESULT = 330  #  ver. >= 7
    CS_OAUTH_TOKEN_REQUEST = 340  #  ver. >= 10
    SC_OAUTH_TOKEN_REQUEST_RESULT = 350  #  ver. >= 10
    SC_CHANNELPACK_UPDATE_B = 360  #  ver. >= 8
    SC_CHANNELPACK_UPDATE_C = 361  #  ver. >= 10
    SC_CHANNELPACK_UPDATE_D = 362  #  ver. >= 15
    SC_CHANNELPACK_UPDATE_E = 363  # ver. >= 23
    SC_CHANNELGROUP_PACK_UPDATE = 380  #  ver. >= 9
    SC_CHANNELGROUP_PACK_UPDATE_B = 381  #  ver. >= 10
    SC_CHANNELGROUP_RELATION_PACK_UPDATE = 390  #  ver. >= 9
    SC_CHANNEL_RELATION_PACK_UPDATE = 395  # ver. >= 21
    SC_CHANNELVALUE_PACK_UPDATE = 400  #  ver. >= 9
    SC_CHANNELVALUE_PACK_UPDATE_B = 401  #  ver. >= 15
    SC_CHANNELEXTENDEDVALUE_PACK_UPDATE = 405  #  ver. >= 10
    CS_SET_VALUE = 410  #  ver. >= 9
    CS_SUPERUSER_AUTHORIZATION_REQUEST = 420  #  ver. >= 10
    CS_GET_SUPERUSER_AUTHORIZATION_RESULT = 425  #  ver. >= 12
    SC_SUPERUSER_AUTHORIZATION_RESULT = 430  #  ver. >= 10
    CS_DEVICE_CALCFG_REQUEST = 440  #  ver. >= 10
    CS_DEVICE_CALCFG_REQUEST_B = 445  #  ver. >= 11
    SC_DEVICE_CALCFG_RESULT = 450  #  ver. >= 10
    SD_DEVICE_CALCFG_REQUEST = 460  #  ver. >= 10
    DS_DEVICE_CALCFG_RESULT = 470  #  ver. >= 10
    DCS_GET_USER_LOCALTIME = 480  #  ver. >= 11
    DCS_GET_USER_LOCALTIME_RESULT = 490  #  ver. >= 11
    CSD_GET_CHANNEL_STATE = 500  #  ver. >= 12
    DSC_CHANNEL_STATE_RESULT = 510  #  ver. >= 12
    CS_GET_CHANNEL_BASIC_CFG = 520  #  ver. >= 12
    SC_CHANNEL_BASIC_CFG_RESULT = 530  #  ver. >= 12
    CS_SET_CHANNEL_FUNCTION = 540  #  ver. >= 12
    SC_SET_CHANNEL_FUNCTION_RESULT = 550  #  ver. >= 12
    CS_CLIENTS_RECONNECT_REQUEST = 560  #  ver. >= 12
    SC_CLIENTS_RECONNECT_REQUEST_RESULT = 570  #  ver. >= 12
    CS_SET_REGISTRATION_ENABLED = 580  #  ver. >= 12
    SC_SET_REGISTRATION_ENABLED_RESULT = 590  #  ver. >= 12
    CS_DEVICE_RECONNECT_REQUEST = 600  #  ver. >= 12
    SC_DEVICE_RECONNECT_REQUEST_RESULT = 610  #  ver. >= 12
    DS_GET_CHANNEL_FUNCTIONS = 620  #  ver. >= 12
    SD_GET_CHANNEL_FUNCTIONS_RESULT = 630  #  ver. >= 12
    CS_SET_CHANNEL_CAPTION = 640  #  ver. >= 12
    SC_SET_CHANNEL_CAPTION_RESULT = 650  #  ver. >= 12
    CS_SET_CHANNEL_GROUP_CAPTION = 642  #  ver. >= 20
    SC_SET_CHANNEL_GROUP_CAPTION_RESULT = 652  #  ver. >= 20
    CS_SET_LOCATION_CAPTION = 645  #  ver. >= 14
    SC_SET_LOCATION_CAPTION_RESULT = 655  #  ver. >= 14
    DS_GET_CHANNEL_CONFIG = 680  #  ver. >= 16
    SD_GET_CHANNEL_CONFIG_RESULT = 690  #  ver. >= 16
    DS_SET_CHANNEL_CONFIG = 681  # ver. >= 21
    SD_SET_CHANNEL_CONFIG_RESULT = 691  # ver. >= 21
    SD_SET_CHANNEL_CONFIG = 682  # ver. >= 21
    DS_SET_CHANNEL_CONFIG_RESULT = 692  # ver. >= 21
    SD_CHANNEL_CONFIG_FINISHED = 683  # ver. >= 21
    DS_SET_DEVICE_CONFIG = 684  # ver. >= 21
    SD_SET_DEVICE_CONFIG_RESULT = 694  # ver. >= 21
    SD_SET_DEVICE_CONFIG = 685  # ver. >= 21
    DS_SET_DEVICE_CONFIG_RESULT = 695  # ver. >= 21
    DS_ACTIONTRIGGER = 700  #  ver. >= 16
    CS_TIMER_ARM = 800  #  ver. >= 17
    SC_SCENE_PACK_UPDATE = 900  #  ver. >= 18
    SC_SCENE_STATE_PACK_UPDATE = 910  #  ver. >= 18
    CS_EXECUTE_ACTION = 1000  #  ver. >= 19
    CS_EXECUTE_ACTION_WITH_AUTH = 1010  #  ver. >= 19
    SC_ACTION_EXECUTION_RESULT = 1020  #  ver. >= 19
    CS_GET_CHANNEL_VALUE_WITH_AUTH = 1030  #  ver. >= 19
    SC_GET_CHANNEL_VALUE_RESULT = 1040  #  ver. >= 19
    CS_SET_SCENE_CAPTION = 1045  #  ver. >= 19
    SC_SET_SCENE_CAPTION_RESULT = 1055  #  ver. >= 19
    DS_REGISTER_PUSH_NOTIFICATION = 1100  #  ver. >= 20
    DS_SEND_PUSH_NOTIFICATION = 1110  #  ver. >= 20
    CS_REGISTER_PN_CLIENT_TOKEN = 1120  #  ver. >= 20
    SC_REGISTER_PN_CLIENT_TOKEN_RESULT = 1121  #  ver. >= 20
    CS_GET_CHANNEL_CONFIG = 1200  # ver. >= 21
    SC_CHANNEL_CONFIG_UPDATE_OR_RESULT = 1210  # ver. >= 21
    CS_SET_CHANNEL_CONFIG = 1220  # ver. >= 21
    CS_GET_DEVICE_CONFIG = 1240  # ver. >= 21
    SC_DEVICE_CONFIG_UPDATE_OR_RESULT = 1250  # ver. >= 21
    DS_SET_SUBDEVICE_DETAILS = 1260  # ver. >= 25


class ChannelType(Enum):
    BINARYSENSOR = 1000
    SENSORNC = 1010  # DEPRECATED
    DISTANCESENSOR = 1020  # ver. >= 5
    CALLBUTTON = 1500  # ver. >= 4
    RELAYHFD4 = 2000  # DEPRECATED
    RELAYG5LA1A = 2010  # DEPRECATED
    _2XRELAYG5LA1A = 2020  # DEPRECATED
    RELAY = 2900
    THERMOMETERDS18B20 = 3000  # DEPRECATED
    DHT11 = 3010  # ver. >= 4  DEPRECATED
    DHT22 = 3020  # ver. >= 4  DEPRECATED
    DHT21 = 3022  # ver. >= 5  DEPRECATED
    AM2302 = 3030  # ver. >= 4  DEPRECATED
    AM2301 = 3032  # ver. >= 5  DEPRECATED

    THERMOMETER = 3034  # ver. >= 8
    HUMIDITYSENSOR = 3036  # ver. >= 8
    HUMIDITYANDTEMPSENSOR = 3038  # ver. >= 8
    WINDSENSOR = 3042  # ver. >= 8
    PRESSURESENSOR = 3044  # ver. >= 8
    RAINSENSOR = 3048  # ver. >= 8
    WEIGHTSENSOR = 3050  # ver. >= 8
    WEATHER_STATION = 3100  # ver. >= 8

    DIMMER = 4000  # ver. >= 4
    RGBLEDCONTROLLER = 4010  # ver. >= 4
    DIMMERANDRGBLED = 4020  # ver. >= 4

    ELECTRICITY_METER = 5000  # ver. >= 10
    IMPULSE_COUNTER = 5010  # ver. >= 10

    THERMOSTAT = 6000  # ver. >= 11
    THERMOSTAT_HEATPOL_HOMEPLUS = 6010  # ver. >= 11
    HVAC = 6100  # ver. >= 21

    VALVE_OPENCLOSE = 7000  # ver. >= 12
    VALVE_PERCENTAGE = 7010  # ver. >= 12
    BRIDGE = 8000  # ver. >= 12
    GENERAL_PURPOSE_MEASUREMENT = 9000  # ver. >= 23
    GENERAL_PURPOSE_METER = 9010  # ver. >= 23
    ENGINE = 10000  # ver. >= 12
    ACTIONTRIGGER = 11000  # ver. >= 16
    DIGIGLASS = 12000  # ver. >= 12


class ChannelFunc(Enum):
    NONE = 0
    CONTROLLINGTHEGATEWAYLOCK = 10
    CONTROLLINGTHEGATE = 20
    CONTROLLINGTHEGARAGEDOOR = 30
    THERMOMETER = 40
    HUMIDITY = 42
    HUMIDITYANDTEMPERATURE = 45
    OPENINGSENSOR_GATEWAY = 50
    OPENINGSENSOR_GATE = 60
    OPENINGSENSOR_GARAGEDOOR = 70
    NOLIQUIDSENSOR = 80
    CONTROLLINGTHEDOORLOCK = 90
    OPENINGSENSOR_DOOR = 100
    CONTROLLINGTHEROLLERSHUTTER = 110
    CONTROLLINGTHEROOFWINDOW = 115  # ver. >= 13
    OPENINGSENSOR_ROLLERSHUTTER = 120
    OPENINGSENSOR_ROOFWINDOW = 125  # ver. >= 13
    POWERSWITCH = 130
    LIGHTSWITCH = 140
    RING = 150
    ALARM = 160
    NOTIFICATION = 170
    DIMMER = 180
    RGBLIGHTING = 190
    DIMMERANDRGBLIGHTING = 200
    DEPTHSENSOR = 210  # ver. >= 5
    DISTANCESENSOR = 220  # ver. >= 5
    OPENINGSENSOR_WINDOW = 230  # ver. >= 8
    HOTELCARDSENSOR = 235  # ver. >= 21
    ALARMARMAMENTSENSOR = 236  # ver. >= 21
    MAILSENSOR = 240  # ver. >= 8
    WINDSENSOR = 250  # ver. >= 8
    PRESSURESENSOR = 260  # ver. >= 8
    RAINSENSOR = 270  # ver. >= 8
    WEIGHTSENSOR = 280  # ver. >= 8
    WEATHER_STATION = 290  # ver. >= 8
    STAIRCASETIMER = 300  # ver. >= 8
    ELECTRICITY_METER = 310  # ver. >= 10
    IC_ELECTRICITY_METER = 315  # ver. >= 12
    IC_GAS_METER = 320  # ver. >= 10
    IC_WATER_METER = 330  # ver. >= 10
    IC_HEAT_METER = 340  # ver. >= 10
    IC_EVENTS = 350  # ver. >= 21
    IC_SECONDS = 360  # ver. >= 21
    THERMOSTAT_HEATPOL_HOMEPLUS = 410  # ver. >= 11
    HVAC_THERMOSTAT = 420  # ver. >= 21
    HVAC_THERMOSTAT_HEAT_COOL = 422  # ver. >= 21
    HVAC_DRYER = 423  # ver. >= 21
    HVAC_FAN = 424  # ver. >= 21
    HVAC_THERMOSTAT_DIFFERENTIAL = 425  # ver. >= 21
    HVAC_DOMESTIC_HOT_WATER = 426  # ver. >= 21
    VALVE_OPENCLOSE = 500  # ver. >= 12
    VALVE_PERCENTAGE = 510  # ver. >= 12
    GENERAL_PURPOSE_MEASUREMENT = 520  # ver. >= 23
    GENERAL_PURPOSE_METER = 530  # ver. >= 23
    CONTROLLINGTHEENGINESPEED = 600  # ver. >= 12
    ACTIONTRIGGER = 700  # ver. >= 16
    DIGIGLASS_HORIZONTAL = 800  # ver. >= 14
    DIGIGLASS_VERTICAL = 810  # ver. >= 14
    CONTROLLINGTHEFACADEBLIND = 900  #  ver. >= 24
    TERRACE_AWNING = 910  #  ver. >= 24
    PROJECTOR_SCREEN = 920  #  ver. >= 24
    CURTAIN = 930  #  ver. >= 24
    VERTICAL_BLIND = 940  #  ver. >= 24
    ROLLER_GARAGE_DOOR = 950  #  ver. >= 24
    PUMPSWITCH = 960  #  ver. >= 25
    HEATORCOLDSOURCESWITCH = 970  #  ver. >= 25


class ActionCap(IntFlag):
    NONE = 0
    TURN_ON = 1 << 0
    TURN_OFF = 1 << 1
    TOGGLE_x1 = 1 << 2
    TOGGLE_x2 = 1 << 3
    TOGGLE_x3 = 1 << 4
    TOGGLE_x4 = 1 << 5
    TOGGLE_x5 = 1 << 6


class DeviceFlag(Enum):
    CALCFG_ENTER_CFG_MODE = 0x0010  #  ver. >= 17
    SLEEP_MODE_ENABLED = 0x0020  #  ver. >= 18
    CALCFG_SET_TIME = 0x0040  #  ver. >= 21
    DEVICE_CONFIG_SUPPORTED = 0x0080  #  ver. >= 21
    DEVICE_LOCKED = 0x0100  #  ver. >= 22
    CALCFG_SUBDEVICE_PAIRING = 0x0200  #  ver. >= 25
    CALCFG_IDENTIFY_DEVICE = 0x0400  #  ver. >= 25
    CALCFG_RESTART_DEVICE = 0x0800  #  ver. >= 25
    ALWAYS_ALLOW_CHANNEL_DELETION = 0x1000  #  ver. >= 25
    BLOCK_ADDING_CHANNELS_AFTER_DELETION = 0x2000  # ver. >= 25


class ChannelFlag(IntFlag):
    NONE = 0
    ZWAVE_BRIDGE = 0x0001  # ver. >= 12
    IR_BRIDGE = 0x0002  # ver. >= 12
    RF_BRIDGE = 0x0004  # ver. >= 12
    CHART_TYPE_BAR = 0x0010  # ver. >= 12  DEPRECATED
    CHART_DS_TYPE_DIFFERENTAL = 0x0020  # ver. >= 12 DEPRECATED
    CHART_INTERPOLATE_MEASUREMENTS = 0x0040  # ver. >= 12 DEPRECATED
    RS_SBS_AND_STOP_ACTIONS = 0x0080  # ver. >= 17
    RGBW_COMMANDS_SUPPORTED = 0x0100  # ver. >= 21
    RS_AUTO_CALIBRATION = 0x1000  # ver. >= 15
    CALCFG_RESET_COUNTERS = 0x2000  # ver. >= 15
    CALCFG_RECALIBRATE = 0x4000  # ver. >= 15
    CALCFG_IDENTIFY_SUBDEVICE = 0x8000  # ver. >= 25
    CHANNELSTATE = 0x00010000  # ver. >= 12
    PHASE1_UNSUPPORTED = 0x00020000  # ver. >= 12
    PHASE2_UNSUPPORTED = 0x00040000  # ver. >= 12
    PHASE3_UNSUPPORTED = 0x00080000  # ver. >= 12
    TIME_SETTING_NOT_AVAILABLE = 0x00100000  # ver. >= 12
    RSA_ENCRYPTED_PIN_REQUIRED = 0x00200000  # ver. >= 12
    OFFLINE_DURING_REGISTRATION = 0x00400000  # ver. >= 12
    ZIGBEE_BRIDGE = 0x00800000  # ver. >= 12
    COUNTDOWN_TIMER_SUPPORTED = 0x01000000  # ver. >= 12
    LIGHTSOURCELIFESPAN_SETTABLE = 0x02000000  # ver. >= 12
    POSSIBLE_SLEEP_MODE_deprecated = 0x04000000  # ver. >= 12  DEPRECATED
    RUNTIME_CHANNEL_CONFIG_UPDATE = 0x08000000  # ver. >= 21
    WEEKLY_SCHEDULE = 0x10000000  # ver. >= 21
    HAS_PARENT = 0x20000000  # ver. >= 21
    CALCFG_RESTART_SUBDEVICE = 0x40000000  # ver. >= 25
    BATTERY_COVER_AVAILABLE = 0x80000000  # ver. >= 25


TEMPERATURE_NOT_AVAILABLE = -275.0
HUMIDITY_NOT_AVAILABLE = -1


class ResultCode(Enum):
    NONE = 0
    UNSUPORTED = 1
    FALSE = 2
    TRUE = 3
    TEMPORARILY_UNAVAILABLE = 4
    BAD_CREDENTIALS = 5
    LOCATION_CONFLICT = 6
    CHANNEL_CONFLICT = 7
    DEVICE_DISABLED = 8
    ACCESSID_DISABLED = 9
    LOCATION_DISABLED = 10
    CLIENT_DISABLED = 11
    CLIENT_LIMITEXCEEDED = 12
    DEVICE_LIMITEXCEEDED = 13
    GUID_ERROR = 14
    DEVICE_LOCKED = 15  # ver. >= 22
    REGISTRATION_DISABLED = 17
    ACCESSID_NOT_ASSIGNED = 18
    AUTHKEY_ERROR = 19
    NO_LOCATION_AVAILABLE = 20
    USER_CONFLICT = 21  # Deprecated
    UNAUTHORIZED = 22
    AUTHORIZED = 23
    NOT_ALLOWED = 24
    CHANNELNOTFOUND = 25
    UNKNOWN_ERROR = 26
    DENY_CHANNEL_BELONG_TO_GROUP = 27
    DENY_CHANNEL_HAS_SCHEDULE = 28
    DENY_CHANNEL_IS_ASSOCIETED_WITH_SCENE = 29
    DENY_CHANNEL_IS_ASSOCIETED_WITH_ACTION_TRIGGER = 30
    ACCESSID_INACTIVE = 31  # ver. >= 17
    CFG_MODE_REQUESTED = 32  # ver. >= 18
    ACTION_UNSUPPORTED = 33  # ver. >= 19
    SUBJECT_NOT_FOUND = 34  # ver. >= 19
    INCORRECT_PARAMETERS = 35  # ver. >= 19
    CLIENT_NOT_EXISTS = 36  # ver. >= 19
    COUNTRY_REJECTED = 37
    CHANNEL_IS_OFFLINE = 38  # ver. >= 19
    NOT_REGISTERED = 39  # ver. >= 20
    DENY_CHANNEL_IS_ASSOCIETED_WITH_VBT = 40  # >= 20
    DENY_CHANNEL_IS_ASSOCIETED_WITH_PUSH = 41  # >= 20
    RESTART_REQUESTED = 42  # ver. >= 25
    IDENTIFY_REQUESTED = 43  # ver. >= 25
    MALFORMED_EMAIL = 44  # ver. >= ?


class Target(Enum):
    CHANNEL = 0
    GROUP = 1
    IODEVICE = 2


@dataclass
class TimeVal:
    tv_sec: int = field(metadata=c_uint64())
    tv_usec: int = field(metadata=c_uint64())


@dataclass
class ActionTriggerProperties:
    related_channel_number: int = field(metadata=c_uint8())
    disables_local_operation: int = field(metadata=c_uint32())


@dataclass
class TDS_DeviceChannel_C:
    number: int = field(metadata=c_uint8())
    type: ChannelType = field(metadata=c_enum(ctypes.c_int32))
    action_trigger_caps: ActionCap = field(metadata=c_uint32())
    default_func: ChannelFunc = field(metadata=c_int32())
    flags: ChannelFlag = field(metadata=c_int32())
    value: bytes = field(metadata=c_bytes(size=8))


@dataclass
class TDS_RegisterDevice_E:
    email: str = field(metadata=c_string(EMAIL_MAXSIZE))
    authkey: bytes = field(metadata=c_bytes(AUTHKEY_SIZE))
    guid: bytes = field(metadata=c_bytes(GUID_SIZE))
    name: str = field(metadata=c_string(DEVICE_NAME_MAXSIZE))
    soft_ver: str = field(metadata=c_string(SOFTVER_MAXSIZE))
    server_name: str = field(metadata=c_string(SERVER_NAME_MAXSIZE))
    flags: int = field(metadata=c_int32())
    manufacturer_id: int = field(metadata=c_int16())
    product_id: int = field(metadata=c_int16())
    channels: list[TDS_DeviceChannel_C] = field(
        metadata=c_packed_array(size_ctype=ctypes.c_uint8, max_size=CHANNELMAXCOUNT)
    )


@dataclass
class TSD_RegisterDeviceResult:
    result_code: ResultCode = field(metadata=c_enum(ctypes.c_int32))
    activity_timeout: int = field(metadata=c_int8())
    version: int = field(metadata=c_int8())
    version_min: int = field(metadata=c_int8())


@dataclass
class TDCS_PingServer:
    now: TimeVal


@dataclass
class TSDC_PingServerResult:
    now: TimeVal


@dataclass
class TDCS_SetActivityTimeout:
    activity_timeout: int = field(metadata=c_uint8())


@dataclass
class TSDC_SetActivityTimeoutResult:
    activity_timeout: int = field(metadata=c_uint8())
    min: int = field(metadata=c_uint8())
    max: int = field(metadata=c_uint8())


@dataclass
class TSD_ChannelNewValue:
    sender_id: int = field(metadata=c_int32())
    channel_number: int = field(metadata=c_uint8())
    duration_ms: int = field(metadata=c_uint32())
    value: bytes = field(metadata=c_bytes(size=8))


@dataclass
class TDS_ChannelNewValueResult:
    channel_number: int = field(metadata=c_uint8())
    sender_id: int = field(metadata=c_int32())
    success: bool = field(metadata=c_uint8())


@dataclass
class TDS_DeviceChannelValue:
    channel_number: int = field(metadata=c_uint8())
    value: bytes = field(metadata=c_bytes(size=8))


@dataclass
class TDS_DeviceChannelValue_C:
    channel_number: int = field(metadata=c_uint8())
    offline: bool = field(metadata=c_uint8())
    validity_time_sec: int = field(metadata=c_uint32())
    value: bytes = field(metadata=c_bytes(size=8))


@dataclass
class TCS_RegisterClient_D:
    email: str = field(metadata=c_string(EMAIL_MAXSIZE))
    password: str = field(metadata=c_string(PASSWORD_MAXSIZE))
    authkey: bytes = field(metadata=c_bytes(AUTHKEY_SIZE))
    guid: bytes = field(metadata=c_bytes(GUID_SIZE))
    name: str = field(metadata=c_string(DEVICE_NAME_MAXSIZE))
    soft_ver: str = field(metadata=c_string(SOFTVER_MAXSIZE))
    server_name: str = field(metadata=c_string(SERVER_NAME_MAXSIZE))


@dataclass
class TSC_RegisterClientResult_B:
    result_code: ResultCode = field(metadata=c_enum(ctypes.c_int32))
    client_id: int = field(metadata=c_int32())
    location_count: int = field(metadata=c_int16())
    channel_count: int = field(metadata=c_int16())
    channel_group_count: int = field(metadata=c_int16())
    flags: int = field(metadata=c_int32())
    activity_timeout: int = field(metadata=c_int8())
    version: int = field(metadata=c_int8())
    version_min: int = field(metadata=c_int8())


@dataclass
class TSC_RegisterClientResult_D:
    result_code: ResultCode = field(metadata=c_enum(ctypes.c_int32))
    client_id: int = field(metadata=c_int32())
    location_count: int = field(metadata=c_int16())
    channel_count: int = field(metadata=c_int16())
    channel_group_count: int = field(metadata=c_int16())
    scene_count: int = field(metadata=c_int16())
    flags: int = field(metadata=c_int32())
    activity_timeout: int = field(metadata=c_int8())
    version: int = field(metadata=c_int8())
    version_min: int = field(metadata=c_int8())
    server_unix_timestamp: int = field(metadata=c_int32())


@dataclass
class TCS_ClientAuthorizationDetails:
    access_id: int = field(metadata=c_int32())
    access_id_pwd: str = field(metadata=c_string(ACCESSID_PWD_MAXSIZE))
    email: str = field(metadata=c_string(EMAIL_MAXSIZE))
    authkey: bytes = field(metadata=c_bytes(AUTHKEY_SIZE))
    guid: bytes = field(metadata=c_bytes(GUID_SIZE))
    server_name: str = field(metadata=c_string(SERVER_NAME_MAXSIZE))


class Platform(Enum):
    UNKNOWN = 0
    IOS = 1
    ANDROID = 2


@dataclass
class TCS_PnClientToken:
    development_env: int = field(metadata=c_int8())
    platform: Platform = field(metadata=c_int32())
    app_id: int = field(metadata=c_int32())
    profile_name: str = field(metadata=c_string(PN_PROFILE_NAME_MAXSIZE))
    real_token_size: int = field(metadata=c_uint16())
    token: str = field(
        metadata=c_string(size_ctype=ctypes.c_uint16, max_size=PN_CLIENT_TOKEN_MAXSIZE)
    )


@dataclass
class TCS_RegisterPnClientToken:
    auth: TCS_ClientAuthorizationDetails
    token: TCS_PnClientToken


@dataclass
class TSC_RegisterPnClientTokenResult:
    result_code: ResultCode = field(metadata=c_enum(ctypes.c_int32))


@dataclass
class TCS_SuperUserAuthorizationRequest:
    email: str = field(metadata=c_string(EMAIL_MAXSIZE))
    password: str = field(metadata=c_string(PASSWORD_MAXSIZE))


@dataclass
class TSC_SuperUserAuthorizationResult:
    result: ResultCode = field(metadata=c_int32())


@dataclass
class TSC_Location:
    eol: bool = field(metadata=c_uint8())
    id: int = field(metadata=c_int32())
    caption: str = field(
        metadata=c_string(size_ctype=ctypes.c_int32, max_size=LOCATION_CAPTION_MAXSIZE)
    )


@dataclass
class TSC_LocationPack:
    total_left: int = field(metadata=c_int32())
    items: list[TSC_Location] = field(
        metadata=c_packed_array(
            size_ctype=ctypes.c_int32,
            size_field_offset=-1,  # size field is before total_left
            max_size=LOCATIONPACK_MAXCOUNT,
        )
    )


@dataclass
class ChannelValue:
    value: bytes = field(metadata=c_bytes(CHANNELVALUE_SIZE))
    sub_value: bytes = field(metadata=c_bytes(CHANNELVALUE_SIZE))


@dataclass
class ChannelValue_B:
    value: bytes = field(metadata=c_bytes(CHANNELVALUE_SIZE))
    sub_value: bytes = field(metadata=c_bytes(CHANNELVALUE_SIZE))
    sub_value_type: int = field(metadata=c_uint8())


@dataclass
class TSC_Channel:
    eol: bool = field(metadata=c_uint8())
    id: int = field(metadata=c_int32())
    location_id: int = field(metadata=c_int32())
    func: ChannelFunc = field(metadata=c_enum(ctypes.c_int32))
    online: bool = field(metadata=c_uint8())
    value: ChannelValue
    caption: str = field(
        metadata=c_string(size_ctype=ctypes.c_int32, max_size=CHANNEL_CAPTION_MAXSIZE)
    )


@dataclass
class TSC_Channel_D:
    eol: bool = field(metadata=c_uint8())
    id: int = field(metadata=c_int32())
    device_id: int = field(metadata=c_int32())
    location_id: int = field(metadata=c_int32())
    type: ChannelType = field(metadata=c_enum(ctypes.c_int32))
    func: ChannelFunc = field(metadata=c_enum(ctypes.c_int32))
    alt_icon: int = field(metadata=c_int32())
    user_icon: int = field(metadata=c_int32())
    manufacturer_id: int = field(metadata=c_int16())
    product_id: int = field(metadata=c_int16())
    flags: int = field(metadata=c_uint32())
    protocol_version: int = field(metadata=c_uint8())
    online: bool = field(metadata=c_uint8())
    value: ChannelValue_B
    caption: str = field(
        metadata=c_string(size_ctype=ctypes.c_int32, max_size=CHANNEL_CAPTION_MAXSIZE)
    )


@dataclass
class TSC_ChannelPack_D:
    total_left: int = field(metadata=c_int32())
    items: list[TSC_Channel_D] = field(
        metadata=c_packed_array(
            size_ctype=ctypes.c_int32,
            size_field_offset=-1,  # size field is before total_left
            max_size=CHANNELPACK_MAXCOUNT,
        )
    )


@dataclass
class TSC_Scene:
    eol: bool = field(metadata=c_uint8())
    id: int = field(metadata=c_int32())
    location_id: int = field(metadata=c_int32())
    alt_icon: int = field(metadata=c_int32())
    user_icon: int = field(metadata=c_int32())
    caption: str = field(
        metadata=c_string(size_ctype=ctypes.c_int16, max_size=SCENE_CAPTION_MAXSIZE)
    )


@dataclass
class TSC_ScenePack:
    total_left: int = field(metadata=c_int32())
    items: list[TSC_Scene] = field(
        metadata=c_packed_array(
            size_ctype=ctypes.c_int32,
            size_field_offset=-1,  # size field is before total_left
            max_size=SCENE_PACK_MAXCOUNT,
        )
    )


@dataclass
class TSC_ChannelValue:
    eol: bool = field(metadata=c_uint8())
    id: int = field(metadata=c_int32())
    online: bool = field(metadata=c_uint8())


@dataclass
class TSC_ChannelValue_B:
    eol: bool = field(metadata=c_uint8())
    id: int = field(metadata=c_int32())
    online: bool = field(metadata=c_uint8())
    value: ChannelValue_B


@dataclass
class TSC_ChannelValuePack_B:
    total_left: int = field(metadata=c_int32())
    items: list[TSC_ChannelValue_B] = field(
        metadata=c_packed_array(
            size_ctype=ctypes.c_int32,
            size_field_offset=-1,  # size field is before total_left
            max_size=CHANNELVALUE_PACK_MAXCOUNT,
        )
    )


class ActionSubjectType(Enum):
    UNKNOWN = 0
    CHANNEL = 1
    CHANNEL_GROUP = 2
    SCENE = 3
    SCHEDULE = 4


class ActionType(Enum):
    OPEN = 10
    CLOSE = 20
    SHUT = 30
    REVEAL = 40
    REVEAL_PARTIALLY = 50
    SHUT_PARTIALLY = 51
    TURN_ON = 60
    TURN_OFF = 70
    SET_RGBW_PARAMETERS = 80
    OPEN_CLOSE = 90
    STOP = 100
    TOGGLE = 110
    UP_OR_STOP = 140
    DOWN_OR_STOP = 150
    STEP_BY_STEP = 160
    ENABLE = 200
    DISABLE = 210
    SEND = 220
    READ = 1000
    SET = 2000
    EXECUTE = 3000
    INTERRUPT = 3001
    INTERRUPT_AND_EXECUTE = 3002
    COPY = 10100
    FORWARD_OUTSIDE = 10000


@dataclass
class TCS_Action:
    action_id: ActionType = field(metadata=c_enum(ctypes.c_int32))
    subject_id: int = field(metadata=c_int32())
    subject_type: ActionSubjectType = field(metadata=c_enum(ctypes.c_uint8))
    param: bytes = field(
        metadata=c_bytes(size_ctype=ctypes.c_uint16, max_size=ACTION_PARAM_MAXSIZE)
    )


@dataclass
class TSC_ActionExecutionResult:
    result_code: ResultCode = field(metadata=c_enum(ctypes.c_uint8))
    action_id: ActionType = field(metadata=c_enum(ctypes.c_int32))
    subject_id: int = field(metadata=c_int32())
    subject_type: ActionSubjectType = field(metadata=c_enum(ctypes.c_int32))


@dataclass
class TCS_NewValue:
    value_id: int = field(metadata=c_int32())
    target: Target = field(metadata=c_enum(ctypes.c_uint8))
    value: bytes = field(metadata=c_bytes(CHANNELVALUE_SIZE))


@dataclass
class TSDC_RegistrationEnabled:
    client_timestamp: int = field(metadata=c_int32())  #  time >= now == enabled
    iodevice_timestamp: int = field(metadata=c_int32())  #  time >= now == enabled


# Note: TCSD_ChannelStateRequest is split into TCS_ChannelStateRequest and
# TSD_ChannelStateRequest so that we don't need to support union fields
@dataclass
class TCS_ChannelStateRequest:
    sender_id: int = field(metadata=c_int32())
    channel_id: int = field(metadata=c_uint32())


@dataclass
class TSD_ChannelStateRequest:
    sender_id: int = field(metadata=c_int32())
    channel_number: int = field(metadata=c_uint8())
    padding: bytes = field(repr=False, init=False, metadata=c_bytes(size=3))


# Note: TDSC_ChannelState is split into TDS_ChannelState and
# TSC_ChannelState so that we don't need to support union fields
@dataclass
class TDS_ChannelState:
    receiver_id: int = field(metadata=c_int32())
    channel_number: int = field(metadata=c_uint8())
    padding: bytes = field(repr=False, init=False, metadata=c_bytes(size=3))
    fields: ChannelStateField = field(metadata=c_int32())
    default_icon_field: int = field(metadata=c_int32())
    ipv4: int = field(metadata=c_int32())
    mac: bytes = field(metadata=c_bytes(6))
    battery_level: int = field(metadata=c_uint8())
    battery_powered: bool = field(metadata=c_uint8())
    wifi_rssi: int = field(metadata=c_uint8())
    wifi_signal_strength: int = field(metadata=c_uint8())
    bridge_node_online: bool = field(metadata=c_uint8())
    bridge_node_signal_strength: int = field(metadata=c_uint8())
    uptime: int = field(metadata=c_int32())
    connected_uptime: int = field(metadata=c_int32())
    battery_health: int = field(metadata=c_uint8())
    last_connection_reset_cause: int = field(metadata=c_uint8())
    light_source_lifespan: int = field(metadata=c_uint16())
    light_source_operating_time: int = field(metadata=c_int32())
    empty: bytes = field(repr=False, init=False, metadata=c_bytes(size=2))


@dataclass
class TSC_ChannelState:
    receiver_id: int = field(metadata=c_int32())
    channel_id: int = field(metadata=c_int32())
    fields: ChannelStateField = field(metadata=c_int32())
    default_icon_field: int = field(metadata=c_int32())
    ipv4: int = field(metadata=c_int32())
    mac: bytes = field(metadata=c_bytes(6))
    battery_level: int = field(metadata=c_uint8())
    battery_powered: bool = field(metadata=c_uint8())
    wifi_rssi: int = field(metadata=c_uint8())
    wifi_signal_strength: int = field(metadata=c_uint8())
    bridge_node_online: bool = field(metadata=c_uint8())
    bridge_node_signal_strength: int = field(metadata=c_uint8())
    uptime: int = field(metadata=c_int32())
    connected_uptime: int = field(metadata=c_int32())
    battery_health: int = field(metadata=c_uint8())
    last_connection_reset_cause: int = field(metadata=c_uint8())
    light_source_lifespan: int = field(metadata=c_uint16())
    light_source_operating_time: int = field(metadata=c_int32())
    empty: bytes = field(repr=False, init=False, metadata=c_bytes(2))


class ChannelStateField(IntFlag):
    NONE = 0
    IPV4 = 0x0001
    MAC = 0x0002
    BATTERYLEVEL = 0x0004
    BATTERYPOWERED = 0x0008
    WIFIRSSI = 0x0010
    WIFISIGNALSTRENGTH = 0x0020
    BRIDGENODESIGNALSTRENGTH = 0x0040
    UPTIME = 0x0080
    CONNECTIONUPTIME = 0x0100
    BATTERYHEALTH = 0x0200
    BRIDGENODEONLINE = 0x0400
    LASTCONNECTIONRESETCAUSE = 0x0800
    LIGHTSOURCELIFESPAN = 0x1000
    LIGHTSOURCEOPERATINGTIME = 0x2000
    OPERATINGTIME = 0x4000
    SWITCHCYCLECOUNT = 0x8000


class OAuthResultCode(Enum):
    ERROR = 0
    SUCCESS = 1
    TEMPORARILY_UNAVAILABLE = 2


@dataclass
class TSC_OAuthTokenRequestResult:
    result_code: OAuthResultCode = field(metadata=c_uint8())
    token: TSC_OAuthToken


@dataclass
class TSC_OAuthToken:
    expires_in: int = field(metadata=c_int32())
    token: bytes = field(
        metadata=c_bytes(size_ctype=ctypes.c_int32, max_size=OAUTH_TOKEN_MAXSIZE)
    )


@dataclass
class TRelayChannel_Value:
    on: bool = field(metadata=c_uint8())
    flags: int = field(metadata=c_uint16())
    padding: bytes = field(repr=False, init=False, metadata=c_bytes(size=5))


@dataclass
class TDimmerChannel_Value:
    brightness: int = field(metadata=c_uint8())
    padding: bytes = field(repr=False, init=False, metadata=c_bytes(size=7))


@dataclass
class TCS_DeviceCalCfgRequest_B:
    channel_id: int = field(metadata=c_int32())
    target: int = field(metadata=c_uint8())
    command: int = field(metadata=c_int32())
    datatype: int = field(metadata=c_int32())
    data: bytes = field(
        metadata=c_bytes(size_ctype=ctypes.c_uint32, max_size=CALCFG_DATA_MAXSIZE)
    )


@dataclass
class TSC_DeviceCalCfgResult:
    channel_id: int = field(metadata=c_int32())
    command: int = field(metadata=c_int32())
    result: int = field(metadata=c_int32())
    data: bytes = field(
        metadata=c_bytes(size_ctype=ctypes.c_uint32, max_size=CALCFG_DATA_MAXSIZE)
    )


@dataclass
class TSD_DeviceCalCfgRequest:
    sender_id: int = field(metadata=c_int32())
    channel_number: int = field(metadata=c_int32())
    command: int = field(metadata=c_int32())
    super_user_authorized: bool = field(metadata=c_uint8())
    datatype: int = field(metadata=c_int32())
    data: bytes = field(
        metadata=c_bytes(size_ctype=ctypes.c_uint32, max_size=CALCFG_DATA_MAXSIZE)
    )


@dataclass
class TDS_DeviceCalCfgResult:
    receiver_id: int = field(metadata=c_int32())
    channel_number: int = field(metadata=c_int32())
    command: int = field(metadata=c_int32())
    result: int = field(metadata=c_int32())
    data: bytes = field(
        metadata=c_bytes(size_ctype=ctypes.c_uint32, max_size=CALCFG_DATA_MAXSIZE)
    )


# CHANNEL_CONFIG_MAXSIZE = 128  # v. <= 19
CHANNEL_CONFIG_MAXSIZE = 512  # v. >= 21


class ConfigType(Enum):
    DEFAULT = 0
    WEEKLY_SCHEDULE = 2
    ALT_WEEKLY_SCHEDULE = 3
    OCR = 4


class ConfigResult(Enum):
    FALSE = 0
    TRUE = 1
    DATA_ERROR = 2
    TYPE_NOT_SUPPORTED = 3
    FUNCTION_NOT_SUPPORTED = 4
    LOCAL_CONFIG_DISABLED = 5
    NOT_ALLOWED = 6
    DEVICE_NOT_FOUND = 7


@dataclass
class TCS_GetChannelConfigRequest:
    channel_id: int = field(metadata=c_int32())
    config_type: ConfigType = field(metadata=c_uint8())
    flags: int = field(metadata=c_int32())


@dataclass
class TSCS_ChannelConfig:
    channel_id: int = field(metadata=c_int32())
    func: ChannelFunc = field(metadata=c_int32())
    config_type: ConfigType = field(metadata=c_uint8())
    config: bytes = field(
        metadata=c_bytes(size_ctype=ctypes.c_int16, max_size=CHANNEL_CONFIG_MAXSIZE)
    )


@dataclass
class TSC_ChannelConfigUpdateOrResult:
    result: ConfigResult = field(metadata=c_uint8())
    config: TSCS_ChannelConfig


class GeneralPurposeMeasurementChartType(Enum):
    LINEAR = 0
    BAR = 1
    CANDLE = 2


@dataclass
class TChannelConfig_GeneralPurposeMeasurement:
    value_divider: int = field(metadata=c_int32())
    value_multiplier: int = field(metadata=c_int32())
    value_added: int = field(metadata=c_int64())
    value_precision: int = field(metadata=c_uint8())
    unit_before_value: str = field(metadata=c_string(GENERAL_PURPOSE_UNIT_SIZE))
    unit_after_value: str = field(metadata=c_string(GENERAL_PURPOSE_UNIT_SIZE))
    no_space_before_value: bool = field(metadata=c_uint8())
    no_space_after_value: bool = field(metadata=c_uint8())
    keep_history: bool = field(metadata=c_uint8())
    chart_type: GeneralPurposeMeasurementChartType = field(metadata=c_uint8())
    refresh_interval_ms: int = field(metadata=c_uint16())
    default_value_divider: int = field(metadata=c_int32())
    default_value_multiplier: int = field(metadata=c_int32())
    default_value_added: int = field(metadata=c_int64())
    default_value_precision: int = field(metadata=c_uint8())
    default_unit_before_value: str = field(metadata=c_string(GENERAL_PURPOSE_UNIT_SIZE))
    default_unit_after_value: str = field(metadata=c_string(GENERAL_PURPOSE_UNIT_SIZE))
    reserved: bytes = field(repr=False, init=False, metadata=c_bytes(size=8))


@dataclass
class DataPacket:
    start_tag: bytes = field(repr=False, init=False, metadata=c_bytes(value=TAG))
    version: int = field(metadata=c_uint8())
    rr_id: int = field(metadata=c_uint32())
    call_id: Call = field(metadata=c_enum(ctypes.c_uint32))
    data: bytes = field(
        metadata=c_bytes(size_ctype=ctypes.c_uint32, max_size=MAX_DATA_SIZE)
    )
    end_tag: bytes = field(repr=False, init=False, metadata=c_bytes(value=TAG))
