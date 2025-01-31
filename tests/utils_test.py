from collections.abc import Iterable
from typing import Any

import pytest

from suplalite.utils import batched, to_hex


def test_to_hex() -> None:
    assert to_hex(b"\x01\x02\x03\x04\x42\xff") == "0102030442ff"


@pytest.mark.parametrize(
    "xs,n,result",
    (
        ([1, 2, 3, 4], 1, ((1,), (2,), (3,), (4,))),
        ([1, 2, 3, 4], 2, ((1, 2), (3, 4))),
        ([1, 2, 3, 4], 3, ((1, 2, 3), (4,))),
        ([], 3, tuple(tuple())),
        ([1, 2], 10, ((1, 2),)),
    ),
)
def test_batched(xs: Iterable[Any], n: int, result: Iterable[tuple[Any, ...]]) -> None:
    assert tuple(batched(xs, n)) == result


def test_batched_n_too_small() -> None:
    with pytest.raises(ValueError):
        tuple(batched([1, 2, 3], 0))
