"""Navigation helpers shared by the transaction-set readers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, TypeVar

from .engine import ISA_LENGTH
from .simple_xml import Loop, Segment, walk_loops

T = TypeVar("T")


def transactions(root: Loop, tset: str, read: Callable[[Loop], T]) -> list[T]:
    """Every transaction set of ``tset`` in the tree, read by ``read``."""
    found: list[T] = []
    for st_loop in walk_loops(root, "ST_LOOP"):
        st = st_loop.segment("ST")
        if st is None or st.value("ST01") != tset:
            continue
        found.append(read(st_loop))
    return found


def qualifier_pairs(
    segment: Segment, prefix: str, first: int, last: int
) -> dict[str, str]:
    """Qualifier -> value pairs from elements ``prefix``+``first`` up to ``last``."""
    pairs: dict[str, str] = {}
    for index in range(first, last, 2):
        qualifier = segment.value(f"{prefix}{index:02d}")
        value = segment.value(f"{prefix}{index + 1:02d}")
        if qualifier is None and value is None:
            continue
        if qualifier is None or value is None:
            raise ValueError(
                f"{prefix}{index:02d}/{prefix}{index + 1:02d} must come as a pair"
            )
        pairs[qualifier] = value
    return pairs


ISA_SENDER_QUALIFIER: Final = 5  # ISA05
ISA_SENDER_ID: Final = 6  # ISA06
ISA_RECEIVER_QUALIFIER: Final = 7  # ISA07
ISA_RECEIVER_ID: Final = 8  # ISA08
ISA_CONTROL_NUMBER: Final = 13  # ISA13
ISA_USAGE_INDICATOR: Final = 15  # ISA15: T for test, P for production


def _delimiters(text: str) -> tuple[str, str, str]:
    """The interchange without leading blanks, its element separator and terminator.

    An ISA segment has a fixed width, and declares both delimiters in it.
    """
    text = text.lstrip()
    if not text.startswith("ISA") or len(text) <= ISA_LENGTH:
        raise ValueError("not an X12 interchange")
    return text, text[3], text[ISA_LENGTH - 1]


def isa_fields(text: str) -> list[str]:
    """The ISA segment split into its elements, using the delimiters it declares."""
    text, element, __ = _delimiters(text)
    return text[: ISA_LENGTH - 1].split(element)


def isa_sender(text: str) -> tuple[str, str]:
    """The qualifier and ID of whoever sent the interchange (ISA05 and ISA06)."""
    fields = isa_fields(text)
    return fields[ISA_SENDER_QUALIFIER], fields[ISA_SENDER_ID].strip()


def isa_receiver(text: str) -> tuple[str, str]:
    """The qualifier and ID the interchange is addressed to (ISA07 and ISA08)."""
    fields = isa_fields(text)
    return fields[ISA_RECEIVER_QUALIFIER], fields[ISA_RECEIVER_ID].strip()


def isa_control_number(text: str) -> int:
    """The interchange control number (ISA13) as a number."""
    return int(isa_fields(text)[ISA_CONTROL_NUMBER])


def isa_usage_indicator(text: str) -> str:
    """ISA15: ``T`` for test traffic, ``P`` for production."""
    return isa_fields(text)[ISA_USAGE_INDICATOR].strip()


def segments(text: str) -> list[list[str]]:
    """Every segment of the interchange split into its elements."""
    text, element, terminator = _delimiters(text)
    parts = (part.strip() for part in text.split(terminator))
    return [part.split(element) for part in parts if part]


def document_sets(text: str) -> list[tuple[str, str]]:
    """The functional group code (GS01) and set ID (ST01) of every transaction."""
    group = ""
    found: list[tuple[str, str]] = []
    for segment in segments(text):
        if segment[0] == "GS" and len(segment) > 1:
            group = segment[1]
        elif segment[0] == "ST" and len(segment) > 1:
            found.append((group, segment[1]))
    return found
