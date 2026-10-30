"""Functional acknowledgment (997): records in both directions."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Final

from . import outbound
from .engine import SEVERITY_ERROR, Issue, Outcome
from .outbound import Envelope
from .reading import segments as read_segments
from .reading import transactions
from .simple_xml import Loop, Segment

TSET: Final = "997"
ACCEPTED: Final = "A"
ACCEPTED_WITH_ERRORS: Final = "E"
REJECTED: Final = "R"
PARTIALLY_ACCEPTED: Final = "P"  # a group status only: some transactions rejected
TRANSACTION_STATUSES: Final = frozenset({ACCEPTED, ACCEPTED_WITH_ERRORS, REJECTED})
GROUP_STATUSES: Final = TRANSACTION_STATUSES | {PARTIALLY_ACCEPTED}
MAX_REASON_CODES: Final = 5  # AK502..AK506 and AK905..AK909
DATA_ELEMENT_ERROR: Final = "8"  # AK304: the segment has a data element error

# Positions in a split GS segment (the segment id is 0) and ST segment.
GS_FUNCTIONAL_ID: Final = 1
GS_APPLICATION_SENDER: Final = 2
GS_APPLICATION_RECEIVER: Final = 3
GS_CONTROL_NUMBER: Final = 6
ST_SET_ID: Final = 1
ST_CONTROL_NUMBER: Final = 2


@dataclass(frozen=True)
class SegmentError:
    """AK3: a bad segment in the acknowledged transaction."""

    segment_id: str
    position: int
    syntax_code: str = ""


@dataclass(frozen=True)
class AcknowledgedTransaction:
    """AK2 and AK5: one transaction set, its status, segment errors and reasons."""

    tset: str
    control_number: str
    status: str
    errors: tuple[SegmentError, ...] = field(default_factory=tuple)
    reason_codes: tuple[str, ...] = field(default_factory=tuple)  # AK502..AK506


@dataclass(frozen=True)
class Acknowledgment:
    """One 997: the functional group it acknowledges and each transaction in it."""

    functional_id: str
    group_control: str
    status: str
    transactions: tuple[AcknowledgedTransaction, ...] = field(default_factory=tuple)
    reason_codes: tuple[str, ...] = field(default_factory=tuple)  # AK905..AK909


def _check_status(status: str, where: str, allowed: frozenset[str]) -> str:
    if status not in allowed:
        raise ValueError(f"{where} must be one of {sorted(allowed)}, found {status!r}")
    return status


def build_body(ack: Acknowledgment) -> Loop:
    """The body nodes (between the group header and trailer) for one 997."""
    nodes: list[Loop | Segment] = [
        Segment("AK1", {"AK101": ack.functional_id, "AK102": ack.group_control}),
    ]
    for txn in ack.transactions:
        nodes.append(_transaction_loop(txn))
    nodes.append(
        Segment(
            "AK9",
            {
                "AK901": _check_status(ack.status, "AK901", GROUP_STATUSES),
                "AK902": str(len(ack.transactions)),
                "AK903": str(len(ack.transactions)),
                "AK904": str(sum(1 for t in ack.transactions if t.status != REJECTED)),
                **_coded("AK9", 5, ack.reason_codes),
            },
        )
    )
    return Loop("BODY", nodes)


def _transaction_loop(txn: AcknowledgedTransaction) -> Loop:
    nodes: list[Loop | Segment] = [
        Segment("AK2", {"AK201": txn.tset, "AK202": txn.control_number}),
    ]
    for error in txn.errors:
        nodes.append(
            Loop(
                "AK3_LOOP",
                [
                    Segment(
                        "AK3",
                        {
                            "AK301": error.segment_id,
                            "AK302": str(error.position),
                            "AK304": error.syntax_code,
                        },
                    ),
                ],
            )
        )
    status = _check_status(txn.status, "AK501", TRANSACTION_STATUSES)
    nodes.append(
        Segment("AK5", {"AK501": status, **_coded("AK5", 2, txn.reason_codes)})
    )
    return Loop("AK2_LOOP", nodes)


def _coded(segment: str, first: int, codes: tuple[str, ...]) -> dict[str, str]:
    """Reason codes in elements ``segment``+``first`` onward, at most five."""
    return {
        f"{segment}{first + index:02d}": code
        for index, code in enumerate(codes[:MAX_REASON_CODES])
    }


def _read_codes(segment: Segment, prefix: str, first: int) -> tuple[str, ...]:
    values = (
        segment.value(f"{prefix}{first + index:02d}")
        for index in range(MAX_REASON_CODES)
    )
    return tuple(value for value in values if value)


def read_functional_acknowledgments(root: Loop) -> list[Acknowledgment]:
    """Every 997 in a parsed ``x12simple`` tree, in order."""
    return transactions(root, TSET, _acknowledgment)


def _acknowledgment(st_loop: Loop) -> Acknowledgment:
    ak1 = st_loop.segment("AK1")
    ak9 = st_loop.segment("AK9")
    if ak1 is None or ak9 is None:
        raise ValueError("997 needs AK1 and AK9")
    return Acknowledgment(
        functional_id=ak1.required("AK101"),
        group_control=ak1.required("AK102"),
        status=_check_status(ak9.required("AK901"), "AK901", GROUP_STATUSES),
        transactions=tuple(_transaction(loop) for loop in st_loop.loops("AK2_LOOP")),
        reason_codes=_read_codes(ak9, "AK9", 5),
    )


def _transaction(loop: Loop) -> AcknowledgedTransaction:
    ak2 = loop.segment("AK2")
    ak5 = loop.segment("AK5")
    if ak2 is None or ak5 is None:
        raise ValueError("997 transaction needs AK2 and AK5")
    errors = []
    for note in loop.loops("AK3_LOOP"):
        ak3 = note.segment("AK3")
        if ak3 is None:
            raise ValueError("997 AK3 loop has no AK3 segment")
        errors.append(
            SegmentError(
                segment_id=ak3.required("AK301"),
                position=int(ak3.required("AK302")),
                syntax_code=ak3.value("AK304", "") or "",
            )
        )
    return AcknowledgedTransaction(
        tset=ak2.required("AK201"),
        control_number=ak2.required("AK202"),
        status=_check_status(ak5.required("AK501"), "AK501", TRANSACTION_STATUSES),
        errors=tuple(errors),
        reason_codes=_read_codes(ak5, "AK5", 2),
    )


def acknowledge(text: str, outcome: Outcome, envelope: Envelope, map_path: str) -> str:
    """Our detail-level 997 for one inbound interchange, from its validation outcome.

    One 997 acknowledges one functional group, with a status for each transaction
    in it. An error inside a transaction rejects that transaction only; one outside
    every transaction (or none we can place) rejects the whole group.
    """
    segments = read_segments(text)
    groups = [segment for segment in segments if segment[0] == "GS"]
    if len(groups) != 1:
        raise ValueError(
            f"expected one functional group to acknowledge, found {len(groups)}"
        )
    spans = _transaction_spans(segments)
    if not spans:
        raise ValueError("no transaction set to acknowledge")
    # The application codes of the group acknowledged are exchanged (X12 997 rule).
    group = groups[0]
    envelope = replace(
        envelope,
        application_sender=group[GS_APPLICATION_RECEIVER],
        application_receiver=group[GS_APPLICATION_SENDER],
    )
    errors = [issue for issue in outcome.issues if issue.severity == SEVERITY_ERROR]
    group_failed = (not outcome.ok and not errors) or any(
        _span_of(issue, spans) is None for issue in errors
    )
    acknowledged = tuple(
        _acknowledged(segments, span, errors, spans, group_failed) for span in spans
    )
    ack = Acknowledgment(
        functional_id=group[GS_FUNCTIONAL_ID],
        group_control=group[GS_CONTROL_NUMBER],
        status=_group_status(acknowledged),
        transactions=acknowledged,
        reason_codes=_codes(issue for issue in errors if issue.kind == "GS"),
    )
    tree = outbound.interchange(envelope, build_body(ack), "997", "0001")
    return outbound.render(tree, map_path)


def _transaction_spans(segments: list[list[str]]) -> list[tuple[int, int]]:
    """Index of the ST and of the SE (or the last segment) of each transaction."""
    spans: list[tuple[int, int]] = []
    start = None
    for index, segment in enumerate(segments):
        if segment[0] == "ST":
            start = index
        elif segment[0] == "SE" and start is not None:
            spans.append((start, index))
            start = None
    if start is not None:
        spans.append((start, len(segments) - 1))
    return spans


def _span_of(issue: Issue, spans: list[tuple[int, int]]) -> tuple[int, int] | None:
    """The transaction an issue falls in, by its 1-based segment position."""
    position = issue.segment_position
    if not position:
        return None
    return next((s for s in spans if s[0] < position <= s[1] + 1), None)


def _acknowledged(
    segments: list[list[str]],
    span: tuple[int, int],
    errors: list[Issue],
    spans: list[tuple[int, int]],
    group_failed: bool,
) -> AcknowledgedTransaction:
    st = segments[span[0]]
    own = [issue for issue in errors if _span_of(issue, spans) == span]
    in_segments = [issue for issue in own if issue.kind != "ST"]
    return AcknowledgedTransaction(
        tset=st[ST_SET_ID],
        control_number=st[ST_CONTROL_NUMBER],
        status=REJECTED if own or group_failed else ACCEPTED,
        errors=tuple(_error_for(issue, segments, span[0]) for issue in in_segments),
        reason_codes=_codes(issue for issue in own if issue.kind == "ST"),
    )


def _codes(issues: Iterable[Issue]) -> tuple[str, ...]:
    """The distinct codes of these issues, in order, as many as a segment holds."""
    return tuple(dict.fromkeys(i.code for i in issues if i.code))[:MAX_REASON_CODES]


def _group_status(transactions: tuple[AcknowledgedTransaction, ...]) -> str:
    statuses = {transaction.status for transaction in transactions}
    if statuses == {ACCEPTED}:
        return ACCEPTED
    if statuses == {REJECTED}:
        return REJECTED
    return PARTIALLY_ACCEPTED


_MISSING: Final = re.compile(r"\((\w+)\) missing")


def _error_for(issue: Issue, segments: list[list[str]], st_index: int) -> SegmentError:
    """AK3 for one finding. A missing segment is named by its id; otherwise the
    segment found at the reported position is."""
    position = issue.segment_position
    missing = _MISSING.search(issue.message)
    seid = missing.group(1) if missing else segments[position - 1][0]
    code = DATA_ELEMENT_ERROR if issue.kind == "ELE" else issue.code
    return SegmentError(segment_id=seid, position=position - st_index, syntax_code=code)
