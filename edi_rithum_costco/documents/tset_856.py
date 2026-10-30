"""Shipment confirmation (856), Standard Carton: shipment, order, item, pack.

An item either ships (``SN102``) or is cancelled (``SN105``), never both, so a
line that is partly shipped and partly cancelled takes two item loops. An item
shipped in several boxes carries one pack loop per box.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final

from odoo.addons.edi_x12.x12.fields import (
    format_date,
    format_quantity,
    format_time,
    time_code,
)
from odoo.addons.edi_x12.x12.simple_xml import Loop, Segment

TSET: Final = "856"
STRUCTURE_CODE: Final = "0002"  # BSN05: shipment, order, item, packaging
ORIGINAL: Final = "00"  # BSN01
SHIPMENT_ROUTING: Final = "B"  # TD501: origin/delivery carrier
WEIGHT_QUALIFIER: Final = "A3"  # TD106: the shipper's weight
POUNDS: Final = "01"  # TD108
SHIPPED_ON: Final = "011"  # DTM01
INVOICE_QUALIFIER: Final = "IV"  # REF01: the seller's invoice number
REASON_QUALIFIER: Final = "TD"  # REF01: REF02 is the reason for the change
TRACKING_QUALIFIER: Final = "CP"  # MAN01: carrier-assigned package ID
WAREHOUSE: Final = "WH"  # N101: the warehouse the goods shipped from
WAREHOUSE_QUALIFIER: Final = "54"  # N103: N104 is the vendor warehouse ID
VENDOR_QUALIFIER: Final = "VN"  # LIN02: LIN03 is the seller's item number
BUYER_QUALIFIER: Final = "SK"  # LIN04: LIN05 is the buyer's SKU
EACH: Final = "EA"
ITEM_SHIPPED: Final = "AC"  # SN108
ITEM_CANCELLED: Final = "ID"  # SN108


@dataclass(frozen=True)
class ShippedItem:
    """One order line shipped, and the boxes it travelled in."""

    line_number: str  # the buyer's PO line number (LIN01)
    vendor_sku: str  # our item number (LIN03)
    buyer_sku: str  # the buyer's SKU (LIN05)
    quantity: Decimal  # SN102: the total over all its boxes
    tracking_numbers: tuple[str, ...]  # one per box


@dataclass(frozen=True)
class CancelledItem:
    """Units of one order line the seller will not ship, and why."""

    line_number: str
    vendor_sku: str
    buyer_sku: str
    quantity: Decimal  # SN105
    reason: str  # REF02: one of the buyer's cancel reason codes
    note: str = ""  # REF03: free text


@dataclass(frozen=True)
class ShipmentConfirmation:
    """What happened to one purchase order: units shipped and/or cancelled.

    The carrier, weight, warehouse, invoice and ship time are only needed (and
    only written) when something shipped.
    """

    shipment_id: str  # BSN02
    po_number: str
    created_at: datetime  # BSN03 and BSN04
    shipped: tuple[ShippedItem, ...] = ()
    cancelled: tuple[CancelledItem, ...] = ()
    invoice_number: str = ""  # REF*IV
    shipping_method: str = ""  # TD505: the buyer's code for carrier and service
    weight: Decimal = Decimal(0)  # TD107, in pounds
    warehouse: str = ""  # N104: our warehouse ID, as set up in the buyer's system
    shipped_at: datetime | None = None  # timezone-aware


def build_body(confirmation: ShipmentConfirmation) -> Loop:
    """The body nodes (between ST and SE) for one shipment confirmation."""
    _check(confirmation)
    order = Loop(
        "HL_O_LOOP",
        [_hl(2, 1, "O"), Segment("PRF", {"PRF01": confirmation.po_number})],
    )
    if confirmation.shipped:
        order.children.append(
            Segment(
                "REF",
                {"REF01": INVOICE_QUALIFIER, "REF02": confirmation.invoice_number},
            )
        )
    next_id = 3
    for item in confirmation.shipped:
        loop, next_id = _shipped_loop(next_id, item, confirmation.warehouse)
        order.children.append(loop)
    for item in confirmation.cancelled:
        order.children.append(_cancelled_loop(next_id, item))
        next_id += 1
    shipment = Loop("HL_S_LOOP", [_hl(1, None, "S")])
    if confirmation.shipped:
        shipment.children += [
            _weight(confirmation.weight),
            Segment(
                "TD5",
                {"TD501": SHIPMENT_ROUTING, "TD505": confirmation.shipping_method},
            ),
            _shipped_on(confirmation.shipped_at),
        ]
    shipment.children.append(order)
    bsn = Segment(
        "BSN",
        {
            "BSN01": ORIGINAL,
            "BSN02": confirmation.shipment_id,
            "BSN03": format_date(confirmation.created_at),
            "BSN04": format_time(confirmation.created_at),
            "BSN05": STRUCTURE_CODE,
        },
    )
    return Loop("BODY", [bsn, shipment])


def _hl(number: int, parent: int | None, level: str) -> Segment:
    values = {"HL01": str(number), "HL03": level}
    if parent is not None:
        values["HL02"] = str(parent)
    return Segment("HL", values)


def _weight(weight: Decimal) -> Segment:
    return Segment(
        "TD1",
        {
            "TD106": WEIGHT_QUALIFIER,
            "TD107": format_quantity(weight.quantize(Decimal("0.01"))),
            "TD108": POUNDS,
        },
    )


def _shipped_on(moment: datetime) -> Segment:
    return Segment(
        "DTM",
        {
            "DTM01": SHIPPED_ON,
            "DTM02": format_date(moment),
            "DTM03": format_time(moment),
            "DTM04": time_code(moment),
        },
    )


def _lin(item: ShippedItem | CancelledItem) -> Segment:
    return Segment(
        "LIN",
        {
            "LIN01": item.line_number,
            "LIN02": VENDOR_QUALIFIER,
            "LIN03": item.vendor_sku,
            "LIN04": BUYER_QUALIFIER,
            "LIN05": item.buyer_sku,
        },
    )


def _shipped_loop(number: int, item: ShippedItem, warehouse: str) -> tuple[Loop, int]:
    """The item loop and its pack loops; returns the next free HL number."""
    loop = Loop(
        "HL_I_LOOP",
        [
            _hl(number, 2, "I"),
            _lin(item),
            Segment(
                "SN1",
                {
                    "SN102": format_quantity(item.quantity),
                    "SN103": EACH,
                    "SN108": ITEM_SHIPPED,
                },
            ),
            Loop(
                "N1_LOOP",
                [
                    Segment(
                        "N1",
                        {
                            "N101": WAREHOUSE,
                            "N103": WAREHOUSE_QUALIFIER,
                            "N104": warehouse,
                        },
                    )
                ],
            ),
        ],
    )
    next_id = number + 1
    for tracking_number in item.tracking_numbers:
        loop.children.append(
            Loop(
                "HL_P_LOOP",
                [
                    _hl(next_id, number, "P"),
                    Segment(
                        "MAN",
                        {"MAN01": TRACKING_QUALIFIER, "MAN02": tracking_number},
                    ),
                ],
            )
        )
        next_id += 1
    return loop, next_id


def _cancelled_loop(number: int, item: CancelledItem) -> Loop:
    reason = {"REF01": REASON_QUALIFIER, "REF02": item.reason}
    if item.note:
        reason["REF03"] = item.note
    return Loop(
        "HL_I_LOOP",
        [
            _hl(number, 2, "I"),
            _lin(item),
            Segment(
                "SN1",
                {
                    "SN102": "0",
                    "SN103": EACH,
                    "SN105": format_quantity(item.quantity),
                    "SN106": EACH,
                    "SN108": ITEM_CANCELLED,
                },
            ),
            Segment("REF", reason),
        ],
    )


def _check(confirmation: ShipmentConfirmation) -> None:
    """Refuse a confirmation that lacks a value the buyer requires."""
    missing = [
        name
        for name, value in (
            ("shipment_id", confirmation.shipment_id),
            ("po_number", confirmation.po_number),
            ("items", confirmation.shipped or confirmation.cancelled),
        )
        if not value
    ]
    if confirmation.shipped:
        missing += [
            name
            for name, value in (
                ("invoice_number", confirmation.invoice_number),
                ("shipping_method", confirmation.shipping_method),
                ("warehouse", confirmation.warehouse),
                ("shipped_at", confirmation.shipped_at),
            )
            if not value
        ]
        if confirmation.weight <= 0:
            missing.append("weight")
    for item in confirmation.shipped:
        if not item.tracking_numbers or not all(item.tracking_numbers):
            missing.append("tracking_number")
        missing += _item_gaps(item)
    for item in confirmation.cancelled:
        if not item.reason:
            missing.append("reason")
        missing += _item_gaps(item)
    if missing:
        raise ValueError(
            "shipment confirmation lacks: " + ", ".join(dict.fromkeys(missing))
        )


def _item_gaps(item: ShippedItem | CancelledItem) -> list[str]:
    gaps = [
        name
        for name, value in (
            ("line_number", item.line_number),
            ("vendor_sku", item.vendor_sku),
            ("buyer_sku", item.buyer_sku),
        )
        if not value
    ]
    if item.quantity <= 0:
        gaps.append("quantity")
    return gaps
