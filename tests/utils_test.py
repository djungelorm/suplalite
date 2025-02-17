from collections.abc import Iterable
from typing import Any

import pytest

from suplalite.utils import IntFlag, batched, to_hex


def test_to_hex() -> None:
    assert to_hex(b"\x01\x02\x03\x04\x42\xff") == "0102030442ff"


@pytest.mark.parametrize(
    "xs,n,result",
    (
        ([1, 2, 3, 4], 1, [(1,), (2,), (3,), (4,)]),
        ([1, 2, 3, 4], 2, [(1, 2), (3, 4)]),
        ([1, 2, 3, 4], 3, [(1, 2, 3), (4,)]),
        ([], 3, [tuple()]),
        ([1, 2], 10, [(1, 2)]),
    ),
)
def test_batched(xs: Iterable[Any], n: int, result: Iterable[tuple[Any, ...]]) -> None:
    assert list(batched(xs, n)) == result


def test_batched_n_too_small() -> None:
    with pytest.raises(ValueError):
        tuple(batched([1, 2, 3], 0))


class MyFlag(IntFlag):
    NONE = 0
    A = 0x1
    B = 0x2
    C = 0x4


class MyFlagWithoutNone(IntFlag):
    A = 0x1
    B = 0x2
    C = 0x4


@pytest.mark.parametrize(
    "flag, string",
    (
        (MyFlag.A, "MyFlag.A"),
        (MyFlag.B, "MyFlag.B"),
        (MyFlag.C, "MyFlag.C"),
        (MyFlag.A | MyFlag.B, "MyFlag.A|B"),
        (MyFlag.C | MyFlag.B, "MyFlag.B|C"),
        (MyFlag.C | MyFlag.C, "MyFlag.C"),
        (MyFlagWithoutNone.A, "MyFlagWithoutNone.A"),
        (MyFlag.NONE, "MyFlag.NONE"),
        (MyFlag(0), "MyFlag.NONE"),
        (MyFlagWithoutNone(0), "MyFlagWithoutNone.0"),
    ),
)
def test_int_flag_format(flag: Any, string: str) -> None:
    assert str(flag) == string
    assert f"{flag}" == string
    assert repr(flag) == "<" + string + ": " + str(flag.value) + ">"
