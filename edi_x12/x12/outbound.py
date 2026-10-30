"""Outbound path: records -> pyx12 XML -> X12 text -> validated output."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from .engine import Issue, validate_document
from .simple_xml import Loop, Segment

COMPONENT_SEPARATOR: Final = ":"
REPETITION_SEPARATOR: Final = "^"
DEFAULT_QUALIFIER: Final = "ZZ"
ENVELOPE_CONTROL_WIDTH: Final = 9


class OutboundError(Exception):
    """The generated document did not validate; ``issues`` says why."""

    def __init__(self, issues: tuple[Issue, ...]) -> None:
        super().__init__("; ".join(str(issue) for issue in issues) or "rejected")
        self.issues = issues


@dataclass(frozen=True)
class Envelope:
    """Who sends what to whom, and when. Control numbers are the caller's."""

    sender_id: str
    receiver_id: str
    control_number: int
    production: bool
    sent_at: datetime
    interchange_version: str
    functional_version: str
    functional_id: str
    sender_qualifier: str = DEFAULT_QUALIFIER
    receiver_qualifier: str = DEFAULT_QUALIFIER
    # GS02 and GS03 when they differ from the interchange IDs.
    application_sender: str = ""
    application_receiver: str = ""

    def __post_init__(self) -> None:
        if not 0 < self.control_number < 10**ENVELOPE_CONTROL_WIDTH:
            raise ValueError("control number must fit in 9 digits")


def _seg(seid: str, *values: str) -> Segment:
    """Segment with elements 01.. in order. Empty strings are left out."""
    return Segment(
        seid=seid,
        values={f"{seid}{i:02d}": v for i, v in enumerate(values, 1) if v != ""},
    )


def _padded(value: str, width: int) -> str:
    if len(value) > width:
        raise ValueError(f"{value!r} is longer than {width} characters")
    return value.ljust(width)


def interchange(
    envelope: Envelope, body: Loop, tset_code: str, tset_control: str
) -> Loop:
    """Wrap one transaction set in the full envelope."""
    if not tset_control.isdigit() or len(tset_control) > 9:
        raise ValueError("ST02 must be a number of up to nine digits")
    control = f"{envelope.control_number:09d}"
    date = envelope.sent_at
    isa = Segment(
        seid="ISA",
        values={
            "ISA01": "00",
            "ISA02": _padded("", 10),
            "ISA03": "00",
            "ISA04": _padded("", 10),
            "ISA05": envelope.sender_qualifier,
            "ISA06": _padded(envelope.sender_id, 15),
            "ISA07": envelope.receiver_qualifier,
            "ISA08": _padded(envelope.receiver_id, 15),
            "ISA09": date.strftime("%y%m%d"),
            "ISA10": date.strftime("%H%M"),
            "ISA11": REPETITION_SEPARATOR
            if envelope.interchange_version == "00501"
            else "U",
            "ISA12": envelope.interchange_version,
            "ISA13": control,
            "ISA14": "0",
            "ISA15": "P" if envelope.production else "T",
            "ISA16": COMPONENT_SEPARATOR,
        },
    )
    gs = _seg(
        "GS",
        envelope.functional_id,
        envelope.application_sender or envelope.sender_id,
        envelope.application_receiver or envelope.receiver_id,
        date.strftime("%Y%m%d"),
        date.strftime("%H%M"),
        control,
        "X",
        envelope.functional_version,
    )
    st = _seg("ST", tset_code, tset_control)
    se = _seg("SE", str(_count_segments(body.children) + 2), tset_control)
    ge = _seg("GE", "1", control)
    iea = _seg("IEA", "1", control)
    group = Loop("GS_LOOP", [gs, Loop("ST_LOOP", [st, *body.children, se]), ge])
    return Loop("ISA_LOOP", [isa, group, iea])


def _count_segments(nodes: list) -> int:
    """Segments in a body, looking inside loops."""
    total = 0
    for node in nodes:
        total += _count_segments(node.children) if isinstance(node, Loop) else 1
    return total


def to_simple_xml(root: Loop) -> str:
    """Serialize a tree as pyx12's ``x12simple`` XML."""
    element = ET.Element("x12simple")
    _emit(root.children, element)
    ET.indent(element, space="  ")
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        + ET.tostring(element, encoding="unicode")
        + "\n"
    )


def _emit(children: list, parent: ET.Element) -> None:
    for child in children:
        if isinstance(child, Loop):
            node = ET.SubElement(parent, "loop", id=child.loop_id)
            _emit(child.children, node)
        else:
            node = ET.SubElement(parent, "seg", id=child.seid)
            for element_id, value in child.values.items():
                if value == "":
                    continue
                ET.SubElement(node, "ele", id=element_id).text = value


def to_x12(simple_xml: str) -> str:
    """pyx12's converter: ``x12simple`` XML to X12 text, our delimiters."""
    from pyx12.xmlx12_simple import convert

    out = io.StringIO()
    convert(io.StringIO(simple_xml), out)
    return out.getvalue()


def render(envelope_tree: Loop, map_path: str) -> str:
    """Convert the tree to X12 and validate it; raise if pyx12 rejects it."""
    text = to_x12(to_simple_xml(envelope_tree))
    outcome = validate_document(text, map_path)
    if not outcome.ok:
        raise OutboundError(outcome.issues)
    return text


__all__ = [
    "Envelope",
    "OutboundError",
    "interchange",
    "render",
    "to_simple_xml",
    "to_x12",
]
