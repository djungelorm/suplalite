from __future__ import annotations

import sys
from collections.abc import Iterable
from enum import IntFlag as _IntFlag
from itertools import islice
from typing import TypeVar, cast


def to_hex(data: bytes) -> str:
    return "".join(f"{value:02x}" for value in bytes(data))


T = TypeVar("T")


def batched(iterable: Iterable[T], n: int = 1) -> Iterable[tuple[T, ...]]:
    if n < 1:
        raise ValueError("n must be at least one")
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch


# Customize IntFlag to print human-readable string when f-strings/format
# See https://github.com/python/cpython/issues/86073
class IntFlag(_IntFlag):
    def __str__(self) -> str:
        if sys.version_info[0] == 3 and sys.version_info[1] == 10:  # pragma: no cover
            names = [
                name
                for name, value in self.__class__.__members__.items()
                if self & value.value != 0
            ]
        else:  # pragma: no cover
            names = cast(list[str], [x.name for x in self])
        if len(names) == 0:
            for name, value in self.__class__.__members__.items():
                if value == 0:
                    names.append(name)
        if len(names) == 0:
            names.append("0")
        return self.__class__.__name__ + "." + "|".join(names)

    def __format__(self, spec: str) -> str:
        return self.__str__()

    def __repr__(self) -> str:
        return "<" + self.__str__() + f": {self.value}>"
