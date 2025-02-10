from __future__ import annotations

import ctypes
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from suplalite import proto

if TYPE_CHECKING:
    from suplalite import device


class Channel:  # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self._device: device.Device | None = None
        self._channel_number: int | None = None

    def set_device(self, device: device.Device, channel_number: int) -> None:
        self._device = device
        self._channel_number = channel_number

    async def update(self) -> None:
        if self._device is not None:
            assert self._channel_number is not None
            await self._device.set_value(self._channel_number, self.encoded_value)

    @property
    def type(self) -> proto.ChannelType:
        raise NotImplementedError  # pragma: no cover

    @property
    def action_trigger_caps(self) -> proto.ActionCap:
        raise NotImplementedError  # pragma: no cover

    @property
    def func(self) -> proto.ChannelFunc:
        raise NotImplementedError  # pragma: no cover

    @property
    def flags(self) -> proto.ChannelFlag:
        raise NotImplementedError  # pragma: no cover

    @property
    def encoded_value(self) -> bytes:
        raise NotImplementedError  # pragma: no cover

    async def set_encoded_value(self, value: bytes) -> bool:
        raise NotImplementedError  # pragma: no cover


class Relay(Channel):
    def __init__(
        self,
        default: bool = False,
        on_change: Callable[[Relay, bool], Awaitable[None]] | None = None,
        func: proto.ChannelFunc = proto.ChannelFunc.POWERSWITCH,
    ):
        super().__init__()
        self._value = default
        self._on_change = on_change
        self._func = func

    @property
    def value(self) -> bool:
        return self._value

    @property
    def type(self) -> proto.ChannelType:
        return proto.ChannelType.RELAY

    @property
    def action_trigger_caps(self) -> proto.ActionCap:
        return (
            proto.ActionCap.TURN_ON
            | proto.ActionCap.TURN_OFF
            | proto.ActionCap.TOGGLE_x1
            | proto.ActionCap.TOGGLE_x2
            | proto.ActionCap.TOGGLE_x3
            | proto.ActionCap.TOGGLE_x4
            | proto.ActionCap.TOGGLE_x5
        )

    @property
    def func(self) -> proto.ChannelFunc:
        return self._func

    @property
    def flags(self) -> proto.ChannelFlag:
        return proto.ChannelFlag.CHANNELSTATE

    async def do_set_value(self, value: bool) -> None:
        self._value = value
        await self.update()

    async def set_value(self, value: bool) -> bool:
        if self._on_change is None:
            await self.do_set_value(value)
        else:
            await self._on_change(self, value)
        return True

    @property
    def encoded_value(self) -> bytes:
        return bytes(ctypes.c_uint64(self._value))

    async def set_encoded_value(self, value: bytes) -> bool:
        decoded_value = bool(ctypes.c_uint64.from_buffer_copy(value).value)
        return await self.set_value(decoded_value)


class Temperature(Channel):
    def __init__(self) -> None:
        super().__init__()
        self._value: float | None = None

    @property
    def value(self) -> float | None:
        return self._value

    @property
    def type(self) -> proto.ChannelType:
        return proto.ChannelType.THERMOMETER

    @property
    def action_trigger_caps(self) -> proto.ActionCap:
        return proto.ActionCap.NONE

    @property
    def func(self) -> proto.ChannelFunc:
        return proto.ChannelFunc.THERMOMETER

    @property
    def flags(self) -> proto.ChannelFlag:
        return proto.ChannelFlag.CHANNELSTATE

    async def set_value(self, value: float) -> bool:
        self._value = value
        await self.update()
        return True

    @property
    def encoded_value(self) -> bytes:
        value = self._value
        if value is None:
            value = proto.TEMPERATURE_NOT_AVAILABLE
        return bytes(ctypes.c_double(value))

    async def set_encoded_value(self, value: bytes) -> bool:
        self._value = ctypes.c_double.from_buffer_copy(value).value
        if self._value == proto.TEMPERATURE_NOT_AVAILABLE:
            self._value = None
        await self.update()
        return True


class Humidity(Channel):
    def __init__(self) -> None:
        super().__init__()
        self._value: float | None = None

    @property
    def value(self) -> float | None:
        return self._value

    @property
    def type(self) -> proto.ChannelType:
        return proto.ChannelType.HUMIDITYSENSOR

    @property
    def action_trigger_caps(self) -> proto.ActionCap:
        return proto.ActionCap.NONE

    @property
    def func(self) -> proto.ChannelFunc:
        return proto.ChannelFunc.HUMIDITY

    @property
    def flags(self) -> proto.ChannelFlag:
        return proto.ChannelFlag.CHANNELSTATE

    async def set_value(self, value: float) -> bool:
        self._value = value
        await self.update()
        return True

    @property
    def encoded_value(self) -> bytes:
        value = self._value
        if value is None:
            value = proto.HUMIDITY_NOT_AVAILABLE
        temp_data = bytes(ctypes.c_int32(int(proto.TEMPERATURE_NOT_AVAILABLE * 1000)))
        humi_data = bytes(ctypes.c_int32(int(value * 1000)))
        return temp_data + humi_data

    async def set_encoded_value(self, value: bytes) -> bool:
        self._value = ctypes.c_int32.from_buffer_copy(value[4:8]).value / 1000
        if self._value == proto.HUMIDITY_NOT_AVAILABLE:
            self._value = None
        await self.update()
        return True


class TemperatureAndHumidity(Channel):
    def __init__(self) -> None:
        super().__init__()
        self._temperature: float | None = None
        self._humidity: float | None = None

    @property
    def temperature(self) -> float | None:
        return self._temperature

    @property
    def humidity(self) -> float | None:
        return self._humidity

    @property
    def type(self) -> proto.ChannelType:
        return proto.ChannelType.HUMIDITYANDTEMPSENSOR

    @property
    def action_trigger_caps(self) -> proto.ActionCap:
        return proto.ActionCap.NONE

    @property
    def func(self) -> proto.ChannelFunc:
        return proto.ChannelFunc.HUMIDITYANDTEMPERATURE

    @property
    def flags(self) -> proto.ChannelFlag:
        return proto.ChannelFlag.CHANNELSTATE

    async def set_temperature(self, value: float) -> bool:
        self._temperature = value
        await self.update()
        return True

    async def set_humidity(self, value: float) -> bool:
        self._humidity = value
        await self.update()
        return True

    @property
    def encoded_value(self) -> bytes:
        temp = self._temperature
        humi = self._humidity
        if temp is None:
            temp = proto.TEMPERATURE_NOT_AVAILABLE
        if humi is None:
            humi = proto.HUMIDITY_NOT_AVAILABLE
        temp_data = bytes(ctypes.c_int32(int(temp * 1000)))
        humi_data = bytes(ctypes.c_int32(int(humi * 1000)))
        return temp_data + humi_data

    async def set_encoded_value(self, value: bytes) -> bool:
        self._temperature = ctypes.c_int32.from_buffer_copy(value[0:4]).value / 1000
        self._humidity = ctypes.c_int32.from_buffer_copy(value[4:8]).value / 1000
        if self._temperature == proto.TEMPERATURE_NOT_AVAILABLE:
            self._temperature = None
        if self._humidity == proto.HUMIDITY_NOT_AVAILABLE:
            self._humidity = None
        await self.update()
        return True


class GeneralPurposeMeasurement(Channel):
    def __init__(
        self,
        default: float = 0.0,
        on_change: (
            Callable[[GeneralPurposeMeasurement, float], Awaitable[None]] | None
        ) = None,
    ):
        super().__init__()
        self._value = default
        self._on_change = on_change

    @property
    def value(self) -> float:
        return self._value

    @property
    def type(self) -> proto.ChannelType:
        return proto.ChannelType.GENERAL_PURPOSE_MEASUREMENT

    @property
    def action_trigger_caps(self) -> proto.ActionCap:
        return proto.ActionCap.NONE

    @property
    def func(self) -> proto.ChannelFunc:
        return proto.ChannelFunc.GENERAL_PURPOSE_MEASUREMENT

    @property
    def flags(self) -> proto.ChannelFlag:
        return proto.ChannelFlag.CHANNELSTATE

    async def do_set_value(self, value: float) -> None:
        self._value = value
        await self.update()

    async def set_value(self, value: float) -> bool:
        if self._on_change is None:
            await self.do_set_value(value)
        else:
            await self._on_change(self, value)
        return True

    @property
    def encoded_value(self) -> bytes:
        return bytes(ctypes.c_double(self._value))

    async def set_encoded_value(self, value: bytes) -> bool:
        decoded_value = bool(ctypes.c_double.from_buffer_copy(value).value)
        return await self.set_value(decoded_value)
