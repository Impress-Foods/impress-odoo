"""Reader for pyx12's ``x12simple`` XML: a generic loop / segment tree."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Final

from defusedxml import ElementTree

ROOT_TAG: Final = "x12simple"


@dataclass(frozen=True)
class Segment:
    """One segment instance: its id and the elements present, keyed by map id."""

    seid: str
    values: dict[str, str] = field(default_factory=dict)

    def value(self, element_id: str, default: str | None = None) -> str | None:
        """Stripped value of ``element_id``, or ``default`` when it is absent."""
        return self.values.get(element_id, default)

    def required(self, element_id: str) -> str:
        """Value of ``element_id``; raises ``KeyError`` when the element is absent."""
        if element_id not in self.values:
            raise KeyError(f"{element_id} is absent from segment {self.seid}")
        return self.values[element_id]


@dataclass
class Loop:
    """One loop instance and its children, in document order."""

    loop_id: str
    children: list[Loop | Segment] = field(default_factory=list)

    def segments(self, seid: str) -> list[Segment]:
        """Direct child segments with this id, in order."""
        return [c for c in self.children if isinstance(c, Segment) and c.seid == seid]

    def segment(self, seid: str) -> Segment | None:
        """First direct child segment with this id, if any."""
        found = self.segments(seid)
        return found[0] if found else None

    def loops(self, loop_id: str) -> list[Loop]:
        """Direct child loops with this id, in order."""
        return [
            c for c in self.children if isinstance(c, Loop) and c.loop_id == loop_id
        ]

    def child_ids(self) -> list[str]:
        """Ids of the direct children, in order (loop ids and segment ids)."""
        return [c.loop_id if isinstance(c, Loop) else c.seid for c in self.children]


def parse(text: str) -> Loop:
    """Parse one ``x12simple`` document into a synthetic root loop."""
    root = ElementTree.fromstring(text.encode("utf-8"))
    if root.tag != ROOT_TAG:
        raise ValueError(f"expected <{ROOT_TAG}>, found <{root.tag}>")
    return _loop(root, ROOT_TAG)


def _loop(element, loop_id: str) -> Loop:
    loop = Loop(loop_id=loop_id)
    for child in element:
        if child.tag == "loop":
            loop.children.append(_loop(child, child.get("id", "")))
        elif child.tag == "seg":
            loop.children.append(_segment(child))
        else:
            raise ValueError(f"unexpected <{child.tag}> under <{element.tag}>")
    return loop


def _segment(element) -> Segment:
    values: dict[str, str] = {}
    for child in element:
        if child.tag != "ele":
            raise ValueError(
                f"unexpected <{child.tag}> inside segment {element.get('id')}"
            )
        text = (child.text or "").strip()
        if text:
            values[child.get("id", "")] = text
    return Segment(seid=element.get("id", ""), values=values)


def walk_loops(root: Loop, loop_id: str) -> Iterator[Loop]:
    """Every loop with this id anywhere under ``root``, in document order."""
    for child in root.children:
        if isinstance(child, Loop):
            if child.loop_id == loop_id:
                yield child
            yield from walk_loops(child, loop_id)
