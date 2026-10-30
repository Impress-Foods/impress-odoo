"""Purchase order (850): inbound records from pyx12's XML."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Final

from odoo.addons.edi_x12.x12.fields import (
    parse_date,
    parse_decimal,
)
from odoo.addons.edi_x12.x12.party import Party, read_ship_to, text_or_empty
from odoo.addons.edi_x12.x12.reading import qualifier_pairs, transactions
from odoo.addons.edi_x12.x12.simple_xml import Loop

TSET: Final = "850"
SKU_QUALIFIER: Final = "SK"
DESCRIPTION_TYPE: Final = "08"  # PID02 of the product description
PACKING_SLIP_QUALIFIER: Final = "PK"  # REF01: REF03 is the packing slip language
FIRST_IDENTIFIER: Final = 8  # PO108 starts the qualifier/value pairs
LAST_ELEMENT: Final = 25  # the map carries PO101..PO125


@dataclass(frozen=True)
class OrderLine:
    """One PO1 line: quantity, unit, price, SKU, description and identifiers."""

    line_number: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    sku: str
    identifiers: dict[str, str] = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True)
class PurchaseOrder:
    """One 850: the order header (BEG) and its lines."""

    purpose: str
    order_type: str
    po_number: str
    created_on: date
    lines: tuple[OrderLine, ...] = field(default_factory=tuple)
    ship_to: Party | None = None
    shipping_method: str = ""  # TD505: the carrier and service the buyer asks for
    packing_slip_language: str = ""  # REF*PK REF03: EN or FR


def read_purchase_orders(root: Loop) -> list[PurchaseOrder]:
    """Every 850 transaction set in a parsed ``x12simple`` tree, in order."""
    return transactions(root, TSET, _order)


def _order(st_loop: Loop) -> PurchaseOrder:
    beg = st_loop.segment("BEG")
    if beg is None:
        raise ValueError("850 has no BEG segment")
    lines = tuple(_line(loop) for loop in st_loop.loops("PO1_LOOP"))
    ship_to = next(
        (party for loop in st_loop.loops("N1_LOOP") if (party := read_ship_to(loop))),
        None,
    )
    return PurchaseOrder(
        purpose=beg.required("BEG01"),
        order_type=beg.required("BEG02"),
        po_number=beg.required("BEG03"),
        created_on=parse_date(beg.required("BEG05"), "BEG05"),
        lines=lines,
        ship_to=ship_to,
        shipping_method=text_or_empty(st_loop.segment("TD5"), "TD505"),
        packing_slip_language=_packing_slip_language(st_loop),
    )


def _packing_slip_language(st_loop: Loop) -> str:
    for ref in st_loop.segments("REF"):
        if ref.value("REF01") == PACKING_SLIP_QUALIFIER:
            return ref.value("REF03") or ""
    return ""


def _line(loop: Loop) -> OrderLine:
    po1 = loop.segment("PO1")
    if po1 is None:
        raise ValueError("850 item loop has no PO1")
    if po1.value("PO106") != SKU_QUALIFIER:
        raise ValueError(
            f"PO106 must be {SKU_QUALIFIER!r}, found {po1.value('PO106')!r}"
        )
    return OrderLine(
        line_number=po1.required("PO101"),
        quantity=parse_decimal(po1.required("PO102"), "PO102"),
        unit=po1.required("PO103"),
        unit_price=parse_decimal(po1.required("PO104"), "PO104"),
        sku=po1.required("PO107"),
        identifiers=qualifier_pairs(po1, "PO1", FIRST_IDENTIFIER, LAST_ELEMENT),
        description=_description(loop),
    )


def _description(loop: Loop) -> str:
    """Every product description of the item (PID02 08), one per line, in order.

    Costco sends each description in each language, so the item carries several.
    """
    texts = []
    for pid_loop in loop.loops("PID_LOOP"):
        pid = pid_loop.segment("PID")
        if pid is not None and pid.value("PID02") == DESCRIPTION_TYPE:
            texts.append((pid.value("PID05") or "").rstrip(" "))
    return "\n".join(text for text in texts if text)
