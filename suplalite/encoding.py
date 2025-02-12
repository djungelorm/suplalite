from __future__ import annotations

import ctypes
import dataclasses
import importlib
import typing
from enum import Enum
from typing import Any, Protocol, TypeVar, cast


def c_int8() -> dict[str, Any]:
    return {
        "ctype": ctypes.c_int8,
        "encoder": _encode_ctype,
        "decoder": _decode_ctype,
    }


def c_int16() -> dict[str, Any]:
    return {
        "ctype": ctypes.c_int16,
        "encoder": _encode_ctype,
        "decoder": _decode_ctype,
    }


def c_int32() -> dict[str, Any]:
    return {
        "ctype": ctypes.c_int32,
        "encoder": _encode_ctype,
        "decoder": _decode_ctype,
    }


def c_int64() -> dict[str, Any]:
    return {
        "ctype": ctypes.c_int64,
        "encoder": _encode_ctype,
        "decoder": _decode_ctype,
    }


def c_uint8() -> dict[str, Any]:
    return {
        "ctype": ctypes.c_uint8,
        "encoder": _encode_ctype,
        "decoder": _decode_ctype,
    }


def c_uint16() -> dict[str, Any]:
    return {
        "ctype": ctypes.c_uint16,
        "encoder": _encode_ctype,
        "decoder": _decode_ctype,
    }


def c_uint32() -> dict[str, Any]:
    return {
        "ctype": ctypes.c_uint32,
        "encoder": _encode_ctype,
        "decoder": _decode_ctype,
    }


def c_uint64() -> dict[str, Any]:
    return {
        "ctype": ctypes.c_uint64,
        "encoder": _encode_ctype,
        "decoder": _decode_ctype,
    }


def c_double() -> dict[str, Any]:
    return {
        "ctype": ctypes.c_double,
        "encoder": _encode_ctype,
        "decoder": _decode_ctype,
    }


def c_enum(ctype: type) -> dict[str, Any]:
    return {
        "ctype": ctype,
        "encoder": _encode_ctype,
        "decoder": _decode_ctype,
    }


def c_bytes(
    size: int | None = None,
    size_ctype: type | None = None,
    max_size: int | None = None,
    value: bytes | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"bytes": True}
    if size is not None:
        metadata["size"] = size
    if size_ctype is not None:
        metadata["size_ctype"] = size_ctype
    if max_size is not None:
        metadata["max_size"] = max_size
    if value is not None:
        assert isinstance(value, bytes)
        assert size is None
        assert size_ctype is None
        assert max_size is None
        metadata["size"] = len(value)
        metadata["value"] = value
    metadata["encoder"] = _encode_bytes
    metadata["decoder"] = _decode_bytes
    return metadata


def c_string(
    size: int | None = None,
    size_ctype: type | None = None,
    max_size: int | None = None,
    null_terminated: bool = True,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"string": True}
    if size is not None:
        metadata["size"] = size
    if size_ctype is not None:
        metadata["size_ctype"] = size_ctype
    if max_size is not None:
        metadata["max_size"] = max_size
        metadata["null_terminated"] = null_terminated
    metadata["encoder"] = _encode_string
    metadata["decoder"] = _decode_string
    return metadata


def c_packed_array(
    size_ctype: type | None,
    max_size: int | None,
    size_field_offset: int = 0,
) -> dict[str, Any]:
    return {
        "packed_array": True,
        "size_ctype": size_ctype,
        "max_size": max_size,
        "size_field_offset": size_field_offset,
        "encoder": _encode_packed_array,
        "decoder": _decode_packed_array,
    }


def _encode_ctype(value: Any, metadata: dict[str, Any]) -> Any:
    ctype = metadata["ctype"]
    if isinstance(value, Enum):
        value = value.value
    return bytes(ctype(value))


def _decode_ctype(
    data: bytes,
    offset: int,
    name: str,  # pylint: disable=unused-argument
    typ: type,  # pylint: disable=unused-argument
    sizes: dict[str, int],  # pylint: disable=unused-argument
    metadata: dict[str, Any],
) -> tuple[Any, int]:
    ctype = metadata["ctype"]
    value = ctype.from_buffer_copy(data, offset)
    return typ(value.value), ctypes.sizeof(ctype)


def _encode_string(value: Any, metadata: dict[str, Any]) -> Any:
    assert isinstance(value, str)
    if "size" in metadata:
        # fixed length string
        return value.encode(encoding="utf-8").ljust(metadata["size"], b"\x00")
    if "max_size" in metadata:
        # variable length string, with size field
        value = value.encode(encoding="utf-8")
        if metadata["null_terminated"]:
            value += b"\x00"
        size = len(value)
        assert size <= metadata["max_size"]
        return value
    assert False  # pragma: no cover


def _decode_string(
    data: bytes,
    offset: int,
    name: str,
    typ: type,  # pylint: disable=unused-argument
    sizes: dict[str, int],
    metadata: dict[str, Any],
) -> tuple[Any, int]:
    if "size" in metadata:
        return (
            data[offset : offset + metadata["size"]]
            .partition(b"\x00")[0]
            .decode(encoding="utf-8"),
            metadata["size"],
        )
    if "max_size" in metadata:
        assert name is not None
        size = sizes[name]
        assert size <= metadata["max_size"]
        length = size if not metadata["null_terminated"] else size - 1
        assert not metadata["null_terminated"] or data[offset + length] == 0
        return data[offset : offset + length].decode(encoding="utf-8"), size
    assert False  # pragma: no cover


def _encode_bytes(value: Any, metadata: dict[str, Any]) -> Any:
    assert isinstance(value, bytes)
    if "size" in metadata:
        # fixed length bytes
        assert len(value) == metadata["size"]
        return value
    if "max_size" in metadata:
        # variable length bytes, with size field
        size = len(value)
        assert size <= metadata["max_size"]
        return value
    assert False  # pragma: no cover


def _decode_bytes(
    data: bytes,
    offset: int,
    name: str,  # pylint: disable=unused-argument
    typ: type,  # pylint: disable=unused-argument
    sizes: dict[str, int],
    metadata: dict[str, Any],
) -> tuple[Any, int]:
    if "value" in metadata:
        # constant value
        value = metadata["value"]
        assert isinstance(value, bytes)
        assert data[offset : offset + len(value)] == value
        return value, len(value)
    if "size" in metadata:
        # fixed sized bytes
        return data[offset : offset + metadata["size"]], metadata["size"]
    if "max_size" in metadata:
        # variable sized bytes
        assert name is not None
        size = sizes[name]
        assert size <= metadata["max_size"]
        return data[offset : offset + size], size
    assert False  # pragma: no cover


def _encode_packed_array(value: Any, metadata: dict[str, Any]) -> Any:
    # list of messages -> packed array
    max_size = metadata["max_size"]
    assert isinstance(value, list)
    assert len(value) <= max_size
    data = b""
    for x in value:
        data += encode(x)
    return data


def _decode_packed_array(
    data: bytes,
    offset: int,
    name: str,
    typ: type,
    sizes: dict[str, int],
    metadata: dict[str, Any],
) -> tuple[Any, int]:
    assert name is not None
    assert typing.get_origin(typ) == list
    typ_args = typing.get_args(typ)
    assert len(typ_args) == 1
    item_type = typ_args[0]
    max_size = metadata["max_size"]
    assert sizes[name] <= max_size

    items = []
    size = 0
    for _ in range(sizes[name]):
        item, item_size = decode(item_type, data[offset + size :])
        items.append(item)
        size += item_size
    return items, size


class MessageProtocol(Protocol):  # pylint: disable=too-few-public-methods
    def __init__(self, *args: Any) -> None: ...  # pragma: no cover


T = TypeVar("T", bound=MessageProtocol)
Fields = list[tuple[str | None, type, bool, dict[str, Any]]]


def fields(cls: type[T]) -> Fields:
    """Expand the dataclass fields into full field specifications"""
    result: Fields = []

    # Note: we import the module that cls is defined in, so that when resolving
    # type hints, other classes defined in that module are found
    module_name = getattr(cls, "__module__", "")
    module = importlib.import_module(module_name)
    types = typing.get_type_hints(cls, localns=module.__dict__)

    for field in dataclasses.fields(cls):  # type: ignore
        # Note: don't use field.type as it is an unresolved string
        # Use typing.get_type_hints instead
        typ = types[field.name]

        if (
            "string" in field.metadata or "bytes" in field.metadata
        ) and "max_size" in field.metadata:
            metadata = {
                "size_for": field.name,
                "ctype": field.metadata["size_ctype"],
                "encoder": _encode_ctype,
                "decoder": _decode_ctype,
            }
            result.append((None, int, False, metadata))
            metadata = dict(field.metadata)
            del metadata["size_ctype"]
            result.append((field.name, typ, field.init, metadata))

        elif "packed_array" in field.metadata:
            # packed array has two constituent fiels: size and data
            # size field can be offset (does not need to occur right next to data)
            offset = field.metadata["size_field_offset"]
            assert offset <= 0  # size must be before data
            metadata = {
                "size_for": field.name,
                "ctype": field.metadata["size_ctype"],
                "encoder": _encode_ctype,
                "decoder": _decode_ctype,
            }
            result.insert(len(result) + offset, (None, int, False, metadata))
            metadata = dict(field.metadata)
            del metadata["size_ctype"]
            del metadata["size_field_offset"]
            result.append((field.name, typ, field.init, metadata))

        else:
            result.append((field.name, typ, field.init, dict(field.metadata)))
    return result


def encode(msg: T) -> bytes:
    result = []
    fields_ = fields(type(msg))
    fields_by_name = {field[0]: field for field in fields_}

    for name, _, init, metadata in fields_:
        if "size_for" in metadata:
            field_value = getattr(msg, metadata["size_for"])
            _, _, _, field_metadata = fields_by_name[metadata["size_for"]]
            value = len(field_value)
            if (
                "string" in field_metadata
                and "max_size" in field_metadata
                and field_metadata["null_terminated"]
            ):
                value += 1
        elif "value" in metadata and metadata["value"] is not None:
            value = metadata["value"]
        elif not init and "bytes" in metadata and "size" in metadata:
            value = b"\x00" * metadata["size"]
        else:
            assert name is not None
            assert init
            value = getattr(msg, name)

        if "encoder" in metadata:
            result.append(metadata["encoder"](value, metadata))
        else:
            result.append(encode(value))

    return b"".join(result)


def decode(cls: type[T], data: bytes) -> tuple[T, int]:
    args = []
    sizes: dict[str, int] = {}
    offset = 0

    for name, typ, init, metadata in fields(cls):
        x, size = _decode_field(data, offset, sizes, name, typ, metadata)
        offset += size
        args.append(x)

        if "size_for" in metadata:
            sizes[metadata["size_for"]] = args[-1]
            assert not init

        if not init:
            args.pop()

    return cls(*args), offset


def partial_decode(cls: type[T], data: bytes, num_fields: int) -> tuple[list[Any], int]:
    args = []
    sizes: dict[str, int] = {}
    offset = 0

    for i, (name, typ, _, metadata) in enumerate(fields(cls)):
        if i == num_fields:
            break

        x, size = _decode_field(data, offset, sizes, name, typ, metadata)
        offset += size
        args.append(x)

        if "size_for" in metadata:
            sizes[metadata["size_for"]] = args[-1]

    return args, offset


def _decode_field(
    data: bytes,
    offset: int,
    sizes: dict[str, int],
    name: str | None,
    typ: type,
    metadata: dict[str, Any],
) -> tuple[Any, int]:
    if "decoder" in metadata:
        return cast(
            tuple[Any, int],
            metadata["decoder"](data, offset, name, typ, sizes, metadata),
        )
    return decode(typ, data[offset:])
