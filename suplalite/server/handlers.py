from __future__ import annotations

import base64
import binascii
import inspect
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Concatenate, ParamSpec, TypeVar

from suplalite import encoding, proto
from suplalite.server.context import (
    BaseContext,
    ClientContext,
    ConnectionContext,
    DeviceContext,
)
from suplalite.server.events import EventContext, EventId
from suplalite.server.state import (
    ChannelState,
    GeneralPurposeMeasurementChannelConfig,
    SceneState,
)
from suplalite.utils import batched, to_hex

HandlerArgs = ParamSpec("HandlerArgs")


@dataclass
class Handler:
    func: Callable[Concatenate[BaseContext, HandlerArgs], Awaitable[Any]]


@dataclass
class EventHandler(Handler):
    event_context: EventContext
    event_id: EventId

    async def handle_event(self, context: BaseContext, payload: Any) -> None:
        num_params = len(inspect.signature(self.func).parameters) - 1
        if payload is None:
            payload = tuple()
        args = list(payload)[:num_params]
        await self.func(context, *args)


@dataclass
class CallHandler(Handler):
    call_id: proto.Call
    result_id: proto.Call | None
    call_type: type[Any] | None


_handlers: list[Handler] = []


def get_handlers() -> list[Handler]:
    return _handlers


CallHandlerFunc = TypeVar("CallHandlerFunc", bound=Callable[..., Any])


def call_handler(
    call_id: proto.Call, result_id: proto.Call | None = None
) -> Callable[[CallHandlerFunc], CallHandlerFunc]:
    def func(handler_func: CallHandlerFunc) -> CallHandlerFunc:
        annotations = inspect.get_annotations(handler_func, eval_str=True)
        call_type = None
        if "msg" in annotations:
            call_type = annotations["msg"]
        _handlers.append(CallHandler(handler_func, call_id, result_id, call_type))
        return handler_func

    return func


EventHandlerFunc = TypeVar("EventHandlerFunc", bound=Callable[..., Any])


def event_handler(
    event_context: EventContext,
    event_id: EventId,
) -> Callable[[EventHandlerFunc], EventHandlerFunc]:
    def func(handler_func: EventHandlerFunc) -> EventHandlerFunc:
        _handlers.append(EventHandler(handler_func, event_context, event_id))
        return handler_func

    return func


#### Device/Client <-> Server


@call_handler(proto.Call.DCS_PING_SERVER, proto.Call.SDC_PING_SERVER_RESULT)
async def ping(
    context: ConnectionContext,  # pylint: disable=unused-argument
) -> proto.TSDC_PingServerResult:
    now = time.time()
    result = proto.TSDC_PingServerResult(
        proto.TimeVal(tv_sec=int(now), tv_usec=int((now - int(now)) * 1000000))
    )
    return result


@call_handler(
    proto.Call.DCS_GET_REGISTRATION_ENABLED,
    proto.Call.SDC_GET_REGISTRATION_ENABLED_RESULT,
)
async def get_registration_enabled(
    context: ConnectionContext,  # pylint:disable=unused-argument
) -> proto.TSDC_RegistrationEnabled:
    # Note: registration is never enabled
    # Devices are registered by the server config
    # Clients are always allowed
    return proto.TSDC_RegistrationEnabled(0, 0)


@call_handler(
    proto.Call.DCS_SET_ACTIVITY_TIMEOUT, proto.Call.SDC_SET_ACTIVITY_TIMEOUT_RESULT
)
async def set_activity_timeout(
    context: ConnectionContext, msg: proto.TDCS_SetActivityTimeout
) -> proto.TSDC_SetActivityTimeoutResult:
    activity_timeout = msg.activity_timeout
    activity_timeout = max(proto.ACTIVITY_TIMEOUT_MIN, activity_timeout)
    activity_timeout = min(proto.ACTIVITY_TIMEOUT_MAX, activity_timeout)
    context.activity_timeout = activity_timeout
    return proto.TSDC_SetActivityTimeoutResult(
        activity_timeout, proto.ACTIVITY_TIMEOUT_MIN, proto.ACTIVITY_TIMEOUT_MAX
    )


#### Device <-> Server


@call_handler(proto.Call.DS_REGISTER_DEVICE_E, proto.Call.SD_REGISTER_DEVICE_RESULT)
async def register_device(
    context: DeviceContext,
    msg: proto.TDS_RegisterDevice_E,
) -> proto.TSD_RegisterDeviceResult:
    try:
        device_id = context.server.state.get_device_id(msg.guid)
    except KeyError:
        context.log(
            f"device not found with guid {to_hex(msg.guid)}", level=logging.WARN
        )
        context.error = True
        return proto.TSD_RegisterDeviceResult(
            proto.ResultCode.FALSE,
            proto.ACTIVITY_TIMEOUT_DEFAULT,
            proto.PROTO_VERSION,
            proto.PROTO_VERSION_MIN,
        )

    device = context.server.state.get_device(device_id)

    if device.manufacturer_id != msg.manufacturer_id:
        context.log(
            "manufacturer id mismatch; "
            f"expected {device.manufacturer_id} got {msg.manufacturer_id}",
            level=logging.WARN,
        )
        context.error = True
        return proto.TSD_RegisterDeviceResult(
            proto.ResultCode.FALSE,
            proto.ACTIVITY_TIMEOUT_DEFAULT,
            proto.PROTO_VERSION,
            proto.PROTO_VERSION_MIN,
        )

    if device.product_id != msg.product_id:
        context.log(
            "product id mismatch; "
            f"expected {device.product_id} got {msg.product_id}",
            level=logging.WARN,
        )
        context.error = True
        return proto.TSD_RegisterDeviceResult(
            proto.ResultCode.FALSE,
            proto.ACTIVITY_TIMEOUT_DEFAULT,
            proto.PROTO_VERSION,
            proto.PROTO_VERSION_MIN,
        )

    channels = context.server.state.get_device_channels(device_id)
    error: str | None = None
    if len(msg.channels) != len(channels):
        error = f"incorrect number of channels; expected {len(channels)} got {len(msg.channels)}"

    for number, (channel_id, channel_msg) in enumerate(zip(channels, msg.channels)):
        channel = context.server.state.get_channel(channel_id)
        if number != channel_msg.number:
            error = "incorrect channel number"
            break
        if channel.type != channel_msg.type:
            error = (
                f"incorrect type for channel number {number}; "
                f"expected {channel.type} got {channel_msg.type}"
            )
            break
        if channel.func != channel_msg.default_func:
            error = (
                f"incorrect function for channel number {number}; "
                f"expected {channel.func} got {channel_msg.default_func}"
            )
            break
        if channel.flags != channel_msg.flags:
            error = (
                f"incorrect flags for channel number {number}; "
                f"expected {channel.flags} got {channel_msg.flags}"
            )
            break

    if error is not None:
        context.log(error, level=logging.WARN)
        context.error = True
        return proto.TSD_RegisterDeviceResult(
            proto.ResultCode.FALSE,
            proto.ACTIVITY_TIMEOUT_DEFAULT,
            proto.PROTO_VERSION,
            proto.PROTO_VERSION_MIN,
        )

    proto_version = context.conn.proto_version
    if not context.server.state.device_connected(
        device_id, proto_version, context.events
    ):
        # failed to connect, the device is already connected
        context.log("device already connected", level=logging.WARN)
        context.error = True
        return proto.TSD_RegisterDeviceResult(
            proto.ResultCode.FALSE,
            proto.ACTIVITY_TIMEOUT_DEFAULT,
            proto.PROTO_VERSION,
            proto.PROTO_VERSION_MIN,
        )

    context.name = f"device[{device.name}]"
    context.replace(DeviceContext(context, guid=msg.guid, device_id=device_id))

    for channel_number, config in enumerate(msg.channels):
        channel_id = device.channel_ids[channel_number]
        context.server.state.set_channel_value(channel_id, config.value)
        await context.server.events.add(
            EventId.CHANNEL_REGISTER_VALUE, (channel_id, config.value)
        )

    await context.server.events.add(EventId.DEVICE_CONNECTED, (device_id,))
    context.log(
        f"registered; {msg.name} {msg.soft_ver} "
        f"proto={proto_version} "
        f"mid={msg.manufacturer_id} "
        f"pid={msg.product_id}"
    )

    return proto.TSD_RegisterDeviceResult(
        proto.ResultCode.TRUE,
        context.activity_timeout,
        proto.PROTO_VERSION,
        proto.PROTO_VERSION_MIN,
    )


@call_handler(proto.Call.DS_DEVICE_CHANNEL_VALUE_CHANGED)
async def device_channel_value_changed(
    context: DeviceContext, msg: proto.TDS_DeviceChannelValue
) -> None:
    await _device_channel_value_changed(context, msg.channel_number, msg.value)


@call_handler(proto.Call.DS_DEVICE_CHANNEL_VALUE_CHANGED_C)
async def device_channel_value_changed_c(
    context: DeviceContext, msg: proto.TDS_DeviceChannelValue_C
) -> None:  # pragma: no cover
    await _device_channel_value_changed(context, msg.channel_number, msg.value)


async def _device_channel_value_changed(
    context: DeviceContext, channel_number: int, value: bytes
) -> None:
    device = context.server.state.get_device(context.device_id)
    channel_id = device.channel_ids[channel_number]
    context.server.state.set_channel_value(channel_id, value)
    await context.server.events.add(EventId.CHANNEL_VALUE_CHANGED, (channel_id, value))


#### Client <-> Server


@call_handler(proto.Call.CS_REGISTER_CLIENT_D, proto.Call.SC_REGISTER_CLIENT_RESULT_D)
async def register_client(
    context: ClientContext,
    msg: proto.TCS_RegisterClient_D,
) -> proto.TSC_RegisterClientResult_D:
    client_id = context.server.state.add_client(msg.guid)

    if not context.server.state.client_connected(client_id, context.events):
        # failed to connect, the client is already connected
        context.log("client already connected", level=logging.WARN)
        context.error = True
        result_code = proto.ResultCode.FALSE

    else:
        context.name = f"client[{msg.name}]"
        context.replace(ClientContext(context, guid=msg.guid, client_id=client_id))

        context.log(f"registered; proto={context.conn.proto_version}")
        await context.server.events.add(EventId.CLIENT_CONNECTED, (client_id,))
        await context.events.add(EventId.SEND_LOCATIONS)
        result_code = proto.ResultCode.TRUE

    channel_count = len(context.server.state.get_channels())
    scene_count = len(context.server.state.get_scenes())

    return proto.TSC_RegisterClientResult_D(
        result_code=result_code,
        client_id=client_id,
        location_count=1,
        channel_count=channel_count,
        channel_group_count=0,
        scene_count=scene_count,
        activity_timeout=context.activity_timeout,
        version=proto.PROTO_VERSION,
        version_min=proto.PROTO_VERSION_MIN,
        server_unix_timestamp=int(time.time()),
    )


@call_handler(
    proto.Call.CS_REGISTER_PN_CLIENT_TOKEN,
    proto.Call.SC_REGISTER_PN_CLIENT_TOKEN_RESULT,
)
async def register_client_push_notification_token(
    context: ClientContext,  # pylint:disable=unused-argument
) -> proto.TSC_RegisterPnClientTokenResult:  # pragma: no cover
    return proto.TSC_RegisterPnClientTokenResult(proto.ResultCode.FALSE)


@call_handler(
    proto.Call.CS_OAUTH_TOKEN_REQUEST, proto.Call.SC_OAUTH_TOKEN_REQUEST_RESULT
)
async def oauth_token_request(
    context: ClientContext,  # pylint:disable=unused-argument
) -> proto.TSC_OAuthTokenRequestResult:

    # Generate a random token (we don't actually do proper oauth, just allow all)
    key = "".join(random.choice("0123456789abcdef") for i in range(86))
    # Include URL for API
    url = f"https://{context.server.host}:{context.server.api_port}"
    token = key.encode() + b"." + base64.b64encode(url.encode()) + b"\x00"

    return proto.TSC_OAuthTokenRequestResult(
        proto.OAuthResultCode.SUCCESS,
        proto.TSC_OAuthToken(
            300,
            token,
        ),
    )


@call_handler(proto.Call.CS_GET_NEXT)
async def client_get_next(
    context: ClientContext,  # pylint:disable=unused-argument
) -> None:  # pragma: no cover
    client = context.server.state.get_client(context.client_id)
    if not client.sent_channels:
        await context.events.add(EventId.SEND_CHANNELS)
    elif not client.sent_scenes:
        await context.events.add(EventId.SEND_SCENES)


async def execute_channel_action(
    context: ClientContext,
    channel: ChannelState,
    action: proto.ActionType,
    params: bytes | None = None,
) -> None:
    if channel.type == proto.ChannelType.RELAY:
        if action == proto.ActionType.TURN_ON:
            value = encoding.encode(
                proto.TRelayChannel_Value(on=True, flags=proto.RelayFlag.NONE)
            )
        elif action == proto.ActionType.TURN_OFF:
            value = encoding.encode(
                proto.TRelayChannel_Value(on=False, flags=proto.RelayFlag.NONE)
            )
        elif action == proto.ActionType.TOGGLE:
            current_value, _ = encoding.decode(proto.TRelayChannel_Value, channel.value)
            value = encoding.encode(
                proto.TRelayChannel_Value(
                    on=not current_value.on, flags=proto.RelayFlag.NONE
                )
            )
        else:
            context.log(
                f"failed to execute action; relay action {action} not supported",
                level=logging.WARN,
            )
            raise RuntimeError
    elif channel.type == proto.ChannelType.DIMMER:
        if action == proto.ActionType.TURN_ON:
            value = channel.last_value or encoding.encode(
                proto.TDimmerChannel_Value(brightness=100)
            )
        elif action == proto.ActionType.TURN_OFF:
            value = encoding.encode(proto.TDimmerChannel_Value(brightness=0))
        elif action == proto.ActionType.SET_RGBW_PARAMETERS:
            assert params is not None
            rgbw_params, _ = encoding.decode(proto.TAction_RGBW_Parameters, params)
            value = encoding.encode(
                proto.TDimmerChannel_Value(brightness=rgbw_params.brightness)
            )
        else:
            context.log(
                f"failed to execute action; dimmer action {action} not supported",
                level=logging.WARN,
            )
            raise RuntimeError
    else:
        context.log(
            f"failed to execute action; channel type {channel.type} not supported",
            level=logging.WARN,
        )
        raise RuntimeError

    context.server.state.set_channel_value(channel.id, value)
    await context.server.events.add(EventId.CHANNEL_SET_VALUE, (channel.id, value))


@call_handler(proto.Call.CS_EXECUTE_ACTION, proto.Call.SC_ACTION_EXECUTION_RESULT)
async def client_execute_action(
    context: ClientContext,
    msg: proto.TCS_Action,
) -> proto.TSC_ActionExecutionResult:

    try:
        if msg.subject_type == proto.ActionSubjectType.CHANNEL:
            channel_id = msg.subject_id
            try:
                channel = context.server.state.get_channel(channel_id)
            except KeyError as exc:
                context.log(
                    f"failed to execute action; channel id {channel_id} does not exist",
                    level=logging.WARN,
                )
                raise RuntimeError from exc
            await execute_channel_action(context, channel, msg.action_id)

        elif msg.subject_type == proto.ActionSubjectType.SCENE:
            scene_id = msg.subject_id
            try:
                scene = context.server.state.get_scene(scene_id)
            except KeyError as exc:
                context.log(
                    f"failed to execute action; scene id {scene_id} does not exist",
                    level=logging.WARN,
                )
                raise RuntimeError from exc

            if msg.action_id == proto.ActionType.EXECUTE:
                for channel_info in scene.channels:
                    channel = context.server.state.get_channel_by_name(
                        channel_info.name
                    )
                    await execute_channel_action(
                        context, channel, channel_info.action, channel_info.params
                    )

            else:
                context.log(
                    f"failed to execute action; {msg.action_id} not implemented",
                    level=logging.WARN,
                )
                raise RuntimeError

        else:
            context.log(
                f"failed to execute action; subject type {msg.subject_type} not supported",
                level=logging.WARN,
            )
            raise RuntimeError

    except RuntimeError:
        return proto.TSC_ActionExecutionResult(
            proto.ResultCode.FALSE, msg.action_id, msg.subject_id, msg.subject_type
        )

    return proto.TSC_ActionExecutionResult(
        proto.ResultCode.TRUE, msg.action_id, msg.subject_id, msg.subject_type
    )


@call_handler(proto.Call.CS_SET_VALUE)
async def client_set_value(context: ClientContext, msg: proto.TCS_NewValue) -> None:
    if msg.target != proto.Target.CHANNEL:
        context.log("failed to set value; target not supported", level=logging.ERROR)
        return
    channel_id = msg.value_id
    value = msg.value

    # check the channel exists
    try:
        context.server.state.get_channel(channel_id)
    except KeyError:
        context.log(
            f"failed to set value; channel id {channel_id} does not exist",
            level=logging.ERROR,
        )
        return

    context.server.state.set_channel_value(channel_id, value)
    await context.server.events.add(EventId.CHANNEL_SET_VALUE, (channel_id, value))


@event_handler(EventContext.DEVICE, EventId.CHANNEL_SET_VALUE)
async def channel_set_value(
    context: DeviceContext, channel_id: int, value: bytes
) -> None:
    device = context.server.state.get_device(context.device_id)
    if channel_id not in device.channel_ids:  # pragma: no cover
        # channel is not on this device, ignore event
        return
    channel_number = device.channel_ids.index(channel_id)
    # Note: ignore set sender id (set to 0) as we don't need to track who requested the
    # value to be set, as all clients are notified of the value change
    await context.conn.send(
        proto.Call.SD_CHANNEL_SET_VALUE,
        proto.TSD_ChannelNewValue(
            sender_id=0,
            channel_number=channel_number,
            duration_ms=0,
            value=value,
        ),
    )


@call_handler(proto.Call.DS_CHANNEL_SET_VALUE_RESULT)
async def channel_set_value_result(
    context: DeviceContext,  # pylint: disable=unused-argument
    msg: proto.TDS_ChannelNewValueResult,  # pylint: disable=unused-argument
) -> None:  # pragma: no cover
    # Note: ignore this, device should also send a CHANNEL_VALUE_CHANGED message
    pass


@event_handler(EventContext.CLIENT, EventId.SEND_LOCATIONS)
async def send_locations(context: ClientContext) -> None:
    msg = proto.TSC_LocationPack(
        total_left=0,
        items=[
            proto.TSC_Location(eol=True, id=1, caption=context.server.location_name)
        ],
    )
    await context.conn.send(proto.Call.SC_LOCATIONPACK_UPDATE, msg)


def build_pack_message(
    items: list[Any], batch_idx: int, build_item: Callable[[Any], Any]
) -> tuple[int, list[Any]]:
    total_left = len(items)
    batches = list(batched(items, proto.CHANNELPACK_MAXCOUNT))
    assert batch_idx < len(batches)

    for idx, batch in enumerate(batches):  # pragma: no branch
        total_left -= len(batch)
        if idx == batch_idx:
            break

    pack = []
    for item in batches[batch_idx]:
        pack.append(build_item(item))

    if total_left == 0 and len(pack) > 0:
        pack[-1].eol = True

    return total_left, pack


@event_handler(EventContext.CLIENT, EventId.SEND_CHANNELS)
async def send_channels(context: ClientContext) -> None:
    client = context.server.state.get_client(context.client_id)
    if client.sent_channels:  # pragma: no cover
        return

    devices = context.server.state.get_devices()
    channels = context.server.state.get_channels()
    channels_list = [channels[id] for id in sorted(channels.keys())]

    def build_item(channel: ChannelState) -> proto.TSC_Channel_E:
        device = devices[channel.device_id]
        config = get_channel_config(context, channel.id)
        crc32 = binascii.crc32(config.config)
        return proto.TSC_Channel_E(
            eol=False,
            id=channel.id,
            device_id=channel.device_id,
            location_id=1,
            type=channel.type,
            func=channel.func,
            alt_icon=channel.alt_icon,
            user_icon=channel.user_icon,
            manufacturer_id=device.manufacturer_id,
            product_id=device.product_id,
            default_config_crc32=crc32,
            flags=channel.flags,
            protocol_version=device.proto_version,
            online=device.online,
            value=proto.ChannelValue_B(
                channel.value,
                b"\x00\x00\x00\x00\x00\x00\x00\x00",
                0,
            ),
            caption=channel.caption,
        )

    total_left, items = build_pack_message(
        channels_list, client.next_channel_batch, build_item
    )
    msg = proto.TSC_ChannelPack_E(total_left=total_left, items=items)
    await context.conn.send(proto.Call.SC_CHANNELPACK_UPDATE_E, msg)
    context.server.state.set_client_next_channel_batch(context.client_id)

    if total_left == 0:
        context.server.state.set_client_sent_channels(context.client_id)


@event_handler(EventContext.CLIENT, EventId.SEND_SCENES)
async def send_scenes(context: ClientContext) -> None:
    client = context.server.state.get_client(context.client_id)
    if client.sent_scenes:  # pragma: no cover
        return

    scenes = context.server.state.get_scenes()
    scenes_list = [scenes[id] for id in sorted(scenes.keys())]

    def build_item(scene: SceneState) -> proto.TSC_Scene:
        return proto.TSC_Scene(
            eol=False,
            id=scene.id,
            location_id=1,
            alt_icon=scene.alt_icon,
            user_icon=scene.user_icon,
            caption=scene.caption,
        )

    total_left, items = build_pack_message(
        scenes_list, client.next_scene_batch, build_item
    )
    msg = proto.TSC_ScenePack(total_left=total_left, items=items)
    await context.conn.send(proto.Call.SC_SCENE_PACK_UPDATE, msg)
    context.server.state.set_client_next_scene_batch(context.client_id)
    if total_left == 0:  # pragma: no branch
        context.server.state.set_client_sent_scenes(context.client_id)


def get_channel_config(
    context: ClientContext, channel_id: int
) -> proto.TSCS_ChannelConfig:
    try:
        channel = context.server.state.get_channel(channel_id)
    except KeyError:
        context.log(
            f"failed to get channel config; channel id {channel_id} does not exist",
            level=logging.ERROR,
        )
        return proto.TSCS_ChannelConfig(
            channel_id=channel_id,
            func=proto.ChannelFunc.NONE,
            config_type=proto.ConfigType.DEFAULT,
            config=b"",
        )

    config = channel.config

    config_result: bytes | None = None
    if isinstance(config, GeneralPurposeMeasurementChannelConfig):
        config_result = encoding.encode(
            proto.TChannelConfig_GeneralPurposeMeasurement(
                value_divider=config.value_divider,
                value_multiplier=config.value_multiplier,
                value_added=config.value_added,
                value_precision=config.value_precision,
                unit_before_value=config.unit_before_value,
                unit_after_value=config.unit_after_value,
                no_space_before_value=config.no_space_before_value,
                no_space_after_value=config.no_space_after_value,
                keep_history=False,
                chart_type=proto.GeneralPurposeMeasurementChartType.LINEAR,
                refresh_interval_ms=0,
                default_value_divider=config.value_divider,
                default_value_multiplier=config.value_multiplier,
                default_value_added=config.value_added,
                default_value_precision=config.value_precision,
                default_unit_before_value=config.unit_before_value,
                default_unit_after_value=config.unit_after_value,
            )
        )

    return proto.TSCS_ChannelConfig(
        channel_id=channel_id,
        func=channel.func,
        config_type=proto.ConfigType.DEFAULT,
        config=config_result or b"",
    )


@call_handler(
    proto.Call.CS_GET_CHANNEL_CONFIG, proto.Call.SC_CHANNEL_CONFIG_UPDATE_OR_RESULT
)
async def client_get_channel_config(
    context: ClientContext, msg: proto.TCS_GetChannelConfigRequest
) -> proto.TSC_ChannelConfigUpdateOrResult:
    config = get_channel_config(context, msg.channel_id)
    return proto.TSC_ChannelConfigUpdateOrResult(
        result=(
            proto.ConfigResult.TRUE
            if len(config.config) > 0
            else proto.ConfigResult.FALSE
        ),
        config=config,
    )


@call_handler(proto.Call.CSD_GET_CHANNEL_STATE)
async def client_get_channel_state(
    context: ClientContext, msg: proto.TCS_ChannelStateRequest
) -> None:
    channel = context.server.state.get_channel(msg.channel_id)
    events = context.server.state.get_device_events(channel.device_id)
    # Note: sender id appears to always be set to 0. It's not the client id,
    # so instead we use the client id from the context
    await events.add(EventId.GET_CHANNEL_STATE, (context.client_id, msg.channel_id))


@event_handler(EventContext.DEVICE, EventId.GET_CHANNEL_STATE)
async def device_get_channel_state(
    context: DeviceContext, sender_id: int, channel_id: int
) -> None:
    device = context.server.state.get_device(context.device_id)
    channel_number = device.channel_ids.index(channel_id)
    msg = proto.TSD_ChannelStateRequest(
        sender_id=sender_id, channel_number=channel_number
    )
    await context.conn.send(proto.Call.CSD_GET_CHANNEL_STATE, msg)


@call_handler(proto.Call.DSC_CHANNEL_STATE_RESULT)
async def device_channel_state_result(
    context: DeviceContext,
    msg: proto.TDS_ChannelState,
) -> None:
    try:
        events = context.server.state.get_client_events(msg.receiver_id)
    except KeyError:
        context.log(f"client id {msg.receiver_id} not found")
        return
    device = context.server.state.get_device(context.device_id)
    channel_id = device.channel_ids[msg.channel_number]
    await events.add(EventId.CHANNEL_STATE_RESULT, (msg, channel_id))


@event_handler(EventContext.CLIENT, EventId.CHANNEL_STATE_RESULT)
async def client_channel_state_result(
    context: ClientContext, device_msg: proto.TDS_ChannelState, channel_id: int
) -> None:
    # copy device->server message to server->client message using encoded form
    # as the messages are almost identical
    msg, _ = encoding.decode(proto.TSC_ChannelState, encoding.encode(device_msg))
    msg.channel_id = channel_id
    await context.conn.send(proto.Call.DSC_CHANNEL_STATE_RESULT, msg)


@call_handler(proto.Call.CS_SUPERUSER_AUTHORIZATION_REQUEST)
async def client_superuser_authorization_request(
    context: ClientContext, msg: proto.TCS_SuperUserAuthorizationRequest
) -> None:
    if context.server.check_authorized(msg.email, msg.password):
        context.log("authorized", level=logging.INFO)
        context.server.state.set_client_authorized(context.client_id)
        result = proto.ResultCode.AUTHORIZED
    else:
        context.log("unauthorized", level=logging.WARN)
        result = proto.ResultCode.UNAUTHORIZED
    result_msg = proto.TSC_SuperUserAuthorizationResult(result=result)
    await context.conn.send(proto.Call.SC_SUPERUSER_AUTHORIZATION_RESULT, result_msg)


@call_handler(proto.Call.CS_DEVICE_CALCFG_REQUEST_B)
async def client_calcfg_request(
    context: ClientContext, msg: proto.TCS_DeviceCalCfgRequest_B
) -> None:
    try:
        channel = context.server.state.get_channel(msg.channel_id)
    except KeyError:
        context.log(
            f"failed calcfg request; channel id {msg.channel_id} does not exist",
            level=logging.ERROR,
        )
        return
    device = context.server.state.get_device(channel.device_id)
    channel_number = device.channel_ids.index(channel.id)
    events = context.server.state.get_device_events(device.id)
    await events.add(EventId.DEVICE_CONFIG, (msg, context.client_id, channel_number))


@event_handler(EventContext.DEVICE, EventId.DEVICE_CONFIG)
async def device_calcfg_request(
    context: DeviceContext,
    device_msg: proto.TCS_DeviceCalCfgRequest_B,
    client_id: int,
    channel_number: int,
) -> None:
    client = context.server.state.get_client(client_id)
    msg = proto.TSD_DeviceCalCfgRequest(
        sender_id=client_id,
        channel_number=channel_number,
        command=device_msg.command,
        super_user_authorized=client.authorized,
        datatype=device_msg.datatype,
        data=device_msg.data,
    )
    await context.conn.send(proto.Call.SD_DEVICE_CALCFG_REQUEST, msg)


@call_handler(proto.Call.DS_DEVICE_CALCFG_RESULT)
async def device_calcfg_result(
    context: DeviceContext, msg: proto.TDS_DeviceCalCfgResult
) -> None:
    client_id = msg.receiver_id
    try:
        context.server.state.get_client(client_id)
    except KeyError:
        context.log(
            f"failed calcfg result; client id {client_id} does not exist",
            level=logging.ERROR,
        )
        return
    channel_number = msg.channel_number
    device = context.server.state.get_device(context.device_id)
    if channel_number >= len(device.channel_ids):
        context.log(
            f"failed calcfg result; channel number {channel_number} does not exist",
            level=logging.ERROR,
        )
        return
    channel_id = device.channel_ids[channel_number]
    events = context.server.state.get_client_events(client_id)
    await events.add(EventId.DEVICE_CONFIG_RESULT, (msg, channel_id))


@event_handler(EventContext.CLIENT, EventId.DEVICE_CONFIG_RESULT)
async def client_calcfg_result(
    context: ClientContext, msg: proto.TDS_DeviceCalCfgResult, channel_id: int
) -> None:
    result_msg = proto.TSC_DeviceCalCfgResult(
        channel_id=channel_id,
        command=msg.command,
        result=msg.result,
        data=msg.data,
    )
    await context.conn.send(proto.Call.SC_DEVICE_CALCFG_RESULT, result_msg)


######################################################


@event_handler(EventContext.CLIENT, EventId.DEVICE_CONNECTED)
@event_handler(EventContext.CLIENT, EventId.DEVICE_DISCONNECTED)
async def device_connected(context: ClientContext, device_id: int) -> None:
    device = context.server.state.get_device(device_id)
    total_left = len(device.channel_ids)

    batches = batched(device.channel_ids, proto.CHANNELVALUE_PACK_MAXCOUNT)
    for batch in batches:
        items = []
        for channel_id in batch:
            channel = context.server.state.get_channel(channel_id)
            items.append(
                proto.TSC_ChannelValue_B(
                    eol=False,
                    id=channel.id,
                    online=device.online,
                    value=proto.ChannelValue_B(
                        channel.value, b"\x00\x00\x00\x00\x00\x00\x00\x00", 0
                    ),
                )
            )
        total_left -= len(items)
        if total_left == 0 and len(items) > 0:  # pragma: no branch
            items[-1].eol = True
        msg = proto.TSC_ChannelValuePack_B(total_left=total_left, items=items)
        await context.conn.send(proto.Call.SC_CHANNELVALUE_PACK_UPDATE_B, msg)


@event_handler(EventContext.CLIENT, EventId.CHANNEL_VALUE_CHANGED)
async def channel_value_changed(
    context: ClientContext, channel_id: int, value: bytes
) -> None:
    channel = context.server.state.get_channel(channel_id)
    msg = proto.TSC_ChannelValuePack_B(
        total_left=0,
        items=[
            proto.TSC_ChannelValue_B(
                eol=True,
                id=channel.id,
                online=True,
                value=proto.ChannelValue_B(
                    value=value,
                    sub_value=b"\x00\x00\x00\x00\x00\x00\x00\x00",
                    sub_value_type=0,
                ),
            )
        ],
    )
    await context.conn.send(proto.Call.SC_CHANNELVALUE_PACK_UPDATE_B, msg)
