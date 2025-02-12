from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from suplalite import encoding, proto

if TYPE_CHECKING:  # pragma: no cover
    from suplalite import device


class Channel:  # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self._device: device.Device | None = None
        self._channel_number: int | None = None

    def set_device(self, device: device.Device, channel_number: int) -> None:
        self._device = device
        self._channel_number = channel_number

    async def update(self) -> None:
        if self._device is not None:  # pragma: no branch
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

    async def set_encoded_value(self, data: bytes) -> bool:
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
        return self.encode(self._value)

    async def set_encoded_value(self, data: bytes) -> bool:
        value = self.decode(data)
        return await self.set_value(value)

    @staticmethod
    def encode(value: bool) -> bytes:
        return encoding.encode(
            proto.TRelayChannel_Value(on=value, flags=proto.RelayFlag.NONE)
        )

    @staticmethod
    def decode(data: bytes) -> bool:
        msg, _ = encoding.decode(proto.TRelayChannel_Value, data)
        return msg.on


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
        return self.encode(self._value)

    async def set_encoded_value(self, data: bytes) -> bool:
        self._value = self.decode(data)
        await self.update()
        return True

    @staticmethod
    def encode(value: float | None) -> bytes:
        msg = proto.TTemperatureChannel_Value(
            value=proto.TEMPERATURE_NOT_AVAILABLE_FLOAT
        )
        if value is not None:
            msg.value = value
        return encoding.encode(msg)

    @staticmethod
    def decode(data: bytes) -> float | None:
        msg, _ = encoding.decode(proto.TTemperatureChannel_Value, data)
        if msg.value == proto.TEMPERATURE_NOT_AVAILABLE_FLOAT:
            return None
        return msg.value


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
        return self.encode(self._value)

    async def set_encoded_value(self, data: bytes) -> bool:
        self._value = self.decode(data)
        await self.update()
        return True

    @staticmethod
    def encode(value: float | None) -> bytes:
        msg = proto.TTemperatureAndHumidityChannel_Value(
            temperature=proto.TEMPERATURE_NOT_AVAILABLE_INT,
            humidity=proto.HUMIDITY_NOT_AVAILABLE,
        )
        if value is not None:
            msg.humidity = int(value * 1000)
        return encoding.encode(msg)

    @staticmethod
    def decode(data: bytes) -> float | None:
        msg, _ = encoding.decode(proto.TTemperatureAndHumidityChannel_Value, data)
        if msg.humidity == proto.HUMIDITY_NOT_AVAILABLE:
            return None
        return float(msg.humidity) / 1000


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
        return self.encode(self._temperature, self._humidity)

    async def set_encoded_value(self, data: bytes) -> bool:
        temperature, humidity = self.decode(data)
        self._temperature = temperature
        self._humidity = humidity
        await self.update()
        return True

    @staticmethod
    def encode(temperature: float | None, humidity: float | None) -> bytes:
        msg = proto.TTemperatureAndHumidityChannel_Value(
            temperature=proto.TEMPERATURE_NOT_AVAILABLE_INT,
            humidity=proto.HUMIDITY_NOT_AVAILABLE,
        )
        if temperature is not None:
            msg.temperature = int(temperature * 1000)
        if humidity is not None:
            msg.humidity = int(humidity * 1000)
        return encoding.encode(msg)

    @staticmethod
    def decode(data: bytes) -> tuple[float | None, float | None]:
        msg, _ = encoding.decode(proto.TTemperatureAndHumidityChannel_Value, data)
        temperature = None
        humidity = None
        if msg.temperature != proto.TEMPERATURE_NOT_AVAILABLE_INT:
            temperature = float(msg.temperature) / 1000
        if msg.humidity != proto.HUMIDITY_NOT_AVAILABLE:
            humidity = float(msg.humidity) / 1000
        return temperature, humidity


class GeneralPurposeMeasurement(Channel):
    def __init__(
        self,
        default: float = 0.0,
    ):
        super().__init__()
        self._value = default

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

    async def set_value(self, value: float) -> bool:
        self._value = value
        await self.update()
        return True

    @property
    def encoded_value(self) -> bytes:
        return self.encode(self._value)

    async def set_encoded_value(self, data: bytes) -> bool:
        self._value = self.decode(data)
        await self.update()
        return True

    @staticmethod
    def encode(value: float) -> bytes:
        return encoding.encode(
            proto.TGeneralPurposeMeasurementChannel_Value(value=value)
        )

    @staticmethod
    def decode(data: bytes) -> float:
        msg, _ = encoding.decode(proto.TGeneralPurposeMeasurementChannel_Value, data)
        return msg.value
