from __future__ import annotations

from collections.abc import Iterable
from itertools import islice
from typing import TypeVar


def to_hex(data: bytes) -> str:
    return "".join(f"{value:02x}" for value in bytes(data))


T = TypeVar("T")


def batched(iterable: Iterable[T], n: int = 1) -> Iterable[tuple[T, ...]]:
    if n < 1:
        raise ValueError("n must be at least one")
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch
