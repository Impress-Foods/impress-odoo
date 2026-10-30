"""pyx12 validation engine; the maps come from the caller."""

from __future__ import annotations

import io
import logging
import re
import threading
import unicodedata
from dataclasses import dataclass
from typing import Final, NamedTuple
from xml.sax.saxutils import escape, unescape

_logger = logging.getLogger(__name__)

SEVERITY_ERROR: Final = "error"
SEVERITY_WARN: Final = "warn"


@dataclass(frozen=True)
class Issue:
    """One validation finding: severity, segment position and message.

    ``kind`` (SEG, ELE, ST, GS, ISA) and ``code`` are pyx12's own classification,
    the X12 error code a 997 reports for it.
    """

    severity: str
    segment_position: int | None
    message: str
    kind: str = ""
    code: str = ""

    def __str__(self) -> str:
        where = f"segment {self.segment_position}: " if self.segment_position else ""
        return f"[{self.severity}] {where}{self.message}"


_ACK_FAILURE: Final = "Failed to create 999 response"
# U+FFFD, and its UTF-8 bytes read as cp1252, which is how the partner files carry it.
_REPLACEMENTS: Final = ("�", "ï¿½")
ISA_LENGTH: Final = 106  # ISA is fixed width; its terminator is the 106th character
_PID05: Final = re.compile(r"<ele id='PID05'>(.*?)</ele>", re.DOTALL)
_ENTITIES: Final = {"&apos;": "'", "&quot;": '"'}
_LINE_PAT: Final = re.compile(
    r"^Line:(\d+)\s+(?P<kind>ELE|SEG|ST|ISA|GS):(?P<code>\S*)\s+-\s+(?P<msg>.*)$"
)


@dataclass(frozen=True)
class Outcome:
    """Result of one pyx12 validation run over a full interchange."""

    ok: bool
    issues: tuple[Issue, ...]
    xml: str | None = None

    @property
    def summary(self) -> str:
        """The findings on one line, for a message to a person."""
        return "; ".join(str(issue) for issue in self.issues)


class _Run(NamedTuple):
    """What one pyx12 pass reports: the verdict, its findings and the XML it wrote."""

    ok: bool
    issues: tuple[Issue, ...]
    xml: str | None


class _XmlWriterFailure(Exception):
    """pyx12 failed while writing the XML of a document, not while checking it."""


class _CaptureHandler(logging.Handler):
    """Collect pyx12 log records for one validation call only.

    The handler sits on pyx12's process-wide logger, so it keeps only the records
    emitted by the thread that created it: a validation running in another
    thread must not see this one's findings in its own rejection.
    """

    def __init__(self, records: list[logging.LogRecord]) -> None:
        super().__init__()
        self._records = records
        self._thread = threading.get_ident()

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread == self._thread:
            self._records.append(record)


def _to_issues(records: list[logging.LogRecord]) -> tuple[Issue, ...]:
    """Map captured ``Line:.. kind - message`` records to Issues."""
    issues: list[Issue] = []
    for record in records:
        severity = SEVERITY_ERROR if record.levelno >= logging.ERROR else SEVERITY_WARN
        text = record.getMessage()
        match = _LINE_PAT.match(text)
        if match:
            issues.append(
                Issue(
                    severity=severity,
                    segment_position=int(match.group(1)),
                    message=match.group("msg").strip(),
                    kind=match.group("kind"),
                    code=match.group("code"),
                )
            )
        elif text.startswith(_ACK_FAILURE):
            continue
        elif record.levelno >= logging.WARNING:
            # Keep unplaced findings: a rejection with no reason is worse.
            issues.append(Issue(severity=severity, segment_position=None, message=text))
    return tuple(issues)


def validate_document(text: str, map_path: str) -> Outcome:
    """Validate one interchange against the map folder ``map_path``.

    The XML handed back keeps the partner's own description text (PID05), so
    accented French reaches the mapping even though pyx12 checks an ASCII copy.
    """
    checked = _normalize(text)
    try:
        run = _run(checked, map_path, want_xml=True)
    except _XmlWriterFailure:
        # pyx12's XML writer cannot cope with some invalid documents. Validate again
        # without it so the rejection carries pyx12's findings, not the crash.
        run = _run(checked, map_path, want_xml=False)
    if not run.ok or run.xml is None:
        return Outcome(ok=run.ok, issues=run.issues)
    return Outcome(ok=run.ok, issues=run.issues, xml=_restore_text(run.xml, text))


def _normalize(text: str) -> str:
    """The copy pyx12 checks: trailing spaces dropped, characters made ASCII.

    Trailing spaces in an element carry no meaning. U+FFFD marks text the sender
    could not encode, and accented letters are outside the X12 extended set, so
    both are written in their ASCII form (``?`` where there is none). ISA is left
    alone: its padding is fixed width.
    """
    text = _fold(text)
    if len(text) <= ISA_LENGTH or not text.startswith("ISA"):
        return text
    element, terminator = text[3], text[ISA_LENGTH - 1]
    segments = [
        segment if segment.startswith("ISA") else _strip_elements(segment, element)
        for segment in text.split(terminator)
    ]
    return terminator.join(segments)


def _fold(text: str) -> str:
    for replacement in _REPLACEMENTS:
        text = text.replace(replacement, "?")
    decomposed = unicodedata.normalize("NFKD", text)
    base = "".join(char for char in decomposed if not unicodedata.combining(char))
    return base.encode("ascii", "replace").decode("ascii")


def _restore_text(xml: str, text: str) -> str:
    """Put the partner's own description text back where validation saw ASCII.

    PID05 values are matched to the file's PID segments in order. A value is
    restored only when its original folds to the value pyx12 checked, so any
    mismatch leaves the XML as validated.
    """
    originals = _pid05_values(text)
    matches = list(_PID05.finditer(xml))
    if len(originals) != len(matches):
        return xml
    pieces: list[str] = []
    last = 0
    for match, original in zip(matches, originals, strict=True):
        if _fold(original) != unescape(match.group(1), _ENTITIES):
            continue
        pieces.append(xml[last : match.start(1)])
        pieces.append(escape(original))
        last = match.end(1)
    pieces.append(xml[last:])
    return "".join(pieces)


def _pid05_values(text: str) -> list[str]:
    """PID05 of every PID segment that has one, trailing spaces removed."""
    if len(text) <= ISA_LENGTH or not text.startswith("ISA"):
        return []
    element, terminator = text[3], text[ISA_LENGTH - 1]
    values: list[str] = []
    for segment in text.split(terminator):
        parts = segment.strip().split(element)
        if parts[0] == "PID" and len(parts) > 5 and parts[5].rstrip(" "):
            values.append(parts[5].rstrip(" "))
    return values


def _strip_elements(segment: str, element: str) -> str:
    return element.join(part.rstrip(" ") for part in segment.split(element))


def _run(text: str, map_path: str, want_xml: bool) -> _Run:
    import pyx12.params
    from pyx12 import x12n_document
    from pyx12.errors import EngineError

    options = pyx12.params.params()
    options.set("exclude_external_codes", "")
    xml = io.StringIO() if want_xml else None
    records: list[logging.LogRecord] = []
    capture = _CaptureHandler(records)
    logger = logging.getLogger("pyx12")
    logger.addHandler(capture)
    try:
        try:
            ok = x12n_document.x12n_document(
                param=options,
                src_file=io.StringIO(text),
                fd_997=None,
                fd_html=None,
                fd_xmldoc=xml,
                fd_json=None,
                map_path=map_path,
            )
        except EngineError as error:
            # No map for this ISA12 / GS01 / GS08 combination: reject with a reason.
            return _Run(False, (Issue(SEVERITY_ERROR, None, str(error)),), None)
        except Exception as error:
            if want_xml:
                raise _XmlWriterFailure from error
            # pyx12 raises assorted errors on input it cannot read: reject with the
            # reason, keep the traceback in the log, never raise.
            _logger.exception("pyx12 could not read the document")
            message = (
                f"pyx12 could not read the document: {type(error).__name__}: {error}"
            )
            return _Run(False, (Issue(SEVERITY_ERROR, None, message),), None)
    finally:
        logger.removeHandler(capture)
    xml_text = xml.getvalue() or None if xml is not None else None
    return _Run(ok, _to_issues(records), xml_text)
