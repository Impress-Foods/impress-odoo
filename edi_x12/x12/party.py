"""A named party (N1 with N3 and N4), as read from a transaction set."""

from __future__ import annotations

from dataclasses import dataclass

from .simple_xml import Loop, Segment

SHIP_TO = "ST"


@dataclass(frozen=True)
class Party:
    """A named party and its address."""

    name: str
    address: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""


def read_ship_to(loop: Loop) -> Party | None:
    """The ship-to party in a N1 loop, if it has one (N101 = ST)."""
    n1 = next((n for n in loop.segments("N1") if n.value("N101") == SHIP_TO), None)
    if n1 is None:
        return None
    n3 = loop.segment("N3")
    n4 = loop.segment("N4")
    return Party(
        name=n1.required("N102"),
        address=text_or_empty(n3, "N301"),
        city=text_or_empty(n4, "N401"),
        state=text_or_empty(n4, "N402"),
        postal_code=text_or_empty(n4, "N403"),
        country=text_or_empty(n4, "N404"),
    )


def text_or_empty(segment: Segment | None, element_id: str) -> str:
    if segment is None:
        return ""
    return segment.value(element_id, "") or ""
