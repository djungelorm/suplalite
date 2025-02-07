import ctypes
from dataclasses import dataclass, field
from enum import Enum, IntFlag
from typing import Any

import pytest

from suplalite import encoding
from suplalite.encoding import (
    c_bytes,
    c_enum,
    c_int32,
    c_int64,
    c_packed_array,
    c_string,
    c_uint8,
)


@dataclass
class Int32Message:
    x: int = field(metadata=c_int32())


class MyEnum(Enum):
    FOO = 1
    BAR = 2


class MyFlag(IntFlag):
    FOO = 0x01
    BAR = 0x02
    BAZ = 0x04


@dataclass
class EnumMessage:
    x: MyEnum = field(metadata=c_enum(ctypes.c_int16))


@dataclass
class FlagMessage:
    x: MyFlag = field(metadata=c_enum(ctypes.c_int16))


@dataclass
class FixedBytesMessage:
    x: bytes = field(metadata=c_bytes(size=10))


@dataclass
class VariableBytesMessage:
    x: bytes = field(metadata=c_bytes(size_ctype=ctypes.c_int16, max_size=10))


@dataclass
class FixedStringMessage:
    x: str = field(metadata=c_string(size=10))


@dataclass
class NullTerminatedVariableStringMessage:
    x: str = field(metadata=c_string(size_ctype=ctypes.c_int16, max_size=10))


@dataclass
class NotNullTerminatedVariableStringMessage:
    x: str = field(
        metadata=c_string(size_ctype=ctypes.c_int16, max_size=10, null_terminated=False)
    )


@dataclass
class NestedMessage:
    x: Int32Message
    y: FixedStringMessage


@dataclass
class PackedArrayMessage:
    x: list[Int32Message] = field(
        metadata=c_packed_array(size_ctype=ctypes.c_int16, max_size=10)
    )


@dataclass
class PackedArrayWithFieldOffsetMessage:
    # size for y is before x
    x: int = field(metadata=c_int32())
    y: list[Int32Message] = field(
        metadata=c_packed_array(
            size_ctype=ctypes.c_int16, size_field_offset=-1, max_size=10
        )
    )


@dataclass
class LargerMessage:
    a: int = field(metadata=c_int32())
    b: int = field(metadata=c_int64())
    c: str = field(metadata=c_string(size=10))
    d: bool = field(metadata=c_uint8())
    e: bytes = field(metadata=c_bytes(size_ctype=ctypes.c_int16, max_size=10))


@pytest.mark.parametrize(
    "typ,fields",
    [
        (Int32Message, [("x", int, True, {"ctype": ctypes.c_int32})]),
        (EnumMessage, [("x", MyEnum, True, {"ctype": ctypes.c_int16})]),
        (FlagMessage, [("x", MyFlag, True, {"ctype": ctypes.c_int16})]),
        (FixedBytesMessage, [("x", bytes, True, {"bytes": True, "size": 10})]),
        (
            VariableBytesMessage,
            [
                (None, int, False, {"ctype": ctypes.c_int16, "size_for": "x"}),
                ("x", bytes, True, {"bytes": True, "max_size": 10}),
            ],
        ),
        (FixedStringMessage, [("x", str, True, {"string": True, "size": 10})]),
        (
            NullTerminatedVariableStringMessage,
            [
                (None, int, False, {"ctype": ctypes.c_int16, "size_for": "x"}),
                (
                    "x",
                    str,
                    True,
                    {"string": True, "max_size": 10, "null_terminated": True},
                ),
            ],
        ),
        (
            NotNullTerminatedVariableStringMessage,
            [
                (None, int, False, {"ctype": ctypes.c_int16, "size_for": "x"}),
                (
                    "x",
                    str,
                    True,
                    {"string": True, "max_size": 10, "null_terminated": False},
                ),
            ],
        ),
        (
            NestedMessage,
            [
                ("x", Int32Message, True, {}),
                ("y", FixedStringMessage, True, {}),
            ],
        ),
        (
            PackedArrayMessage,
            [
                (None, int, False, {"ctype": ctypes.c_int16, "size_for": "x"}),
                ("x", list[Int32Message], True, {"packed_array": True, "max_size": 10}),
            ],
        ),
        (
            PackedArrayWithFieldOffsetMessage,
            [
                (None, int, False, {"ctype": ctypes.c_int16, "size_for": "y"}),
                ("x", int, True, {"ctype": ctypes.c_int32}),
                ("y", list[Int32Message], True, {"packed_array": True, "max_size": 10}),
            ],
        ),
    ],
)
def test_fields(
    typ: type, fields: list[tuple[str | None, type, bool, dict[str, Any]]]
) -> None:
    actual_fields = []
    for field_ in encoding.fields(typ):
        if "encoder" in field_[3]:
            del field_[3]["encoder"]
        if "decoder" in field_[3]:
            del field_[3]["decoder"]
        actual_fields.append(field_)

    assert fields == actual_fields


@pytest.mark.parametrize(
    "typ,args,data",
    [
        (Int32Message, (0x42,), b"\x42\x00\x00\x00"),
        (EnumMessage, (MyEnum.BAR,), b"\x02\x00"),
        (FlagMessage, (MyFlag.BAR,), b"\x02\x00"),
        (FlagMessage, (MyFlag.FOO | MyFlag.BAZ,), b"\x05\x00"),
        (FixedBytesMessage, (b"foobar\x00\x00\x00\x00",), b"foobar\x00\x00\x00\x00"),
        (VariableBytesMessage, (b"foobar",), b"\x06\x00foobar"),
        (FixedStringMessage, ("foobar",), b"foobar\x00\x00\x00\x00"),
        (NullTerminatedVariableStringMessage, ("foobar",), b"\x07\x00foobar\x00"),
        (NotNullTerminatedVariableStringMessage, ("foobar",), b"\x06\x00foobar"),
        (
            NestedMessage,
            (
                Int32Message(0x42),
                FixedStringMessage("foobar"),
            ),
            b"\x42\x00\x00\x00foobar\x00\x00\x00\x00",
        ),
        (
            PackedArrayMessage,
            (
                [
                    Int32Message(1),
                    Int32Message(2),
                    Int32Message(3),
                ],
            ),
            b"\x03\x00\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00",
        ),
        (
            PackedArrayWithFieldOffsetMessage,
            (
                0x42,
                [
                    Int32Message(1),
                    Int32Message(2),
                    Int32Message(3),
                ],
            ),
            b"\x03\x00\x42\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00",
        ),
    ],
)
def test_field_encoding(
    typ: type[encoding.MessageProtocol], args: tuple[Any, ...], data: bytes
) -> None:
    msg = typ(*args)
    assert encoding.encode(msg) == data
    decoded_msg, decoded_size = encoding.decode(typ, data)
    assert decoded_size == len(data)
    assert decoded_msg == msg


def test_null_terminated_fixed_string_with_garbage() -> None:
    decoded_msg, decoded_size = encoding.decode(FixedStringMessage, b"foo\x00123456")
    assert decoded_size == 10
    assert decoded_msg.x == "foo"


def test_partial_decode() -> None:
    data = (
        b"\x01\x00\x00\x00"
        b"\x02\x00\x00\x00\x00\x00\x00\x00"
        b"foo\x00\x00\x00\x00\x00\x00\x00"
        b"\x01"
        b"\x02\x00hi"
    )

    decoded_msg, decoded_size = encoding.decode(LargerMessage, data)
    assert decoded_size == 27
    assert decoded_msg.a == 1
    assert decoded_msg.b == 2
    assert decoded_msg.c == "foo"
    assert decoded_msg.d is True
    assert decoded_msg.e == b"hi"

    data = (
        b"\x01\x00\x00\x00"  #
        b"\x02\x00\x00\x00\x00\x00\x00\x00"  #
        b"fo"  #
    )
    fields, offset = encoding.partial_decode(LargerMessage, data, num_fields=2)
    assert offset == 12
    assert fields[0] == 1
    assert fields[1] == 2

    data = (
        b"\x01\x00\x00\x00"
        b"\x02\x00\x00\x00\x00\x00\x00\x00"
        b"foo\x00\x00\x00\x00\x00\x00\x00"
        b"\x01"
        b"\x02\x00hi"
    )
    fields, offset = encoding.partial_decode(LargerMessage, data, num_fields=6)
    assert offset == 27
    assert fields[0] == 1
    assert fields[1] == 2
    assert fields[2] == "foo"
    assert fields[3] is True
    assert fields[4] == 2
    assert fields[5] == b"hi"

    with pytest.raises(ValueError):
        encoding.partial_decode(LargerMessage, b"\x01\x00\x00\x00", num_fields=6)
