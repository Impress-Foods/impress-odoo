"""A named party (N1 with N3, N4 and PER), as read from a transaction set."""

from __future__ import annotations

from dataclasses import dataclass

from .reading import qualifier_pairs
from .simple_xml import Loop, Segment

SHIP_TO = "ST"
TELEPHONE = "TE"  # PER03, PER05, PER07: the qualifier of a number
EMAIL = "EM"


@dataclass(frozen=True)
class Party:
    """A named party and its address."""

    name: str
    address: str = ""  # N301
    address2: str = ""  # N302
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""
    phone: str = ""  # PER: the first telephone number
    email: str = ""  # PER: the first electronic mail address


def read_ship_to(loop: Loop) -> Party | None:
    """The ship-to party in a N1 loop, if it has one (N101 = ST)."""
    n1 = next((n for n in loop.segments("N1") if n.value("N101") == SHIP_TO), None)
    if n1 is None:
        return None
    n3 = loop.segment("N3")
    n4 = loop.segment("N4")
    numbers = communication_numbers(loop)
    return Party(
        name=n1.required("N102"),
        address=text_or_empty(n3, "N301"),
        address2=text_or_empty(n3, "N302"),
        city=text_or_empty(n4, "N401"),
        state=text_or_empty(n4, "N402"),
        postal_code=text_or_empty(n4, "N403"),
        country=text_or_empty(n4, "N404"),
        phone=numbers.get(TELEPHONE, ""),
        email=numbers.get(EMAIL, ""),
    )


def communication_numbers(loop: Loop) -> dict[str, str]:
    """Qualifier -> number over the PER segments of a loop; the first of each wins.

    A PER carries up to three qualifier/number pairs (PER03/04, PER05/06, PER07/08).
    """
    found: dict[str, str] = {}
    for per in loop.segments("PER"):
        for qualifier, number in qualifier_pairs(per, "PER", 3, 9).items():
            found.setdefault(qualifier, number)
    return found


def text_or_empty(segment: Segment | None, element_id: str) -> str:
    if segment is None:
        return ""
    return segment.value(element_id, "") or ""
