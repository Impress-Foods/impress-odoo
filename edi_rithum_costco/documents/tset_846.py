"""Inventory advice (846): what we have in each warehouse, item by item."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from odoo.addons.edi_x12.x12.fields import format_date
from odoo.addons.edi_x12.x12.simple_xml import Loop, Segment

TSET: Final = "846"
ORIGINAL: Final = "00"  # BIA01
SELLER_INVENTORY_REPORT: Final = "SI"  # BIA02
MERCHANT_QUALIFIER: Final = "IO"  # REF01: REF02 names the party we send to
WAREHOUSE_QUALIFIER: Final = "WS"  # REF01: REF02 is the warehouse, REF03 its quantity
VENDOR_QUALIFIER: Final = "VN"  # LIN02: LIN03 is the seller's item number
BUYER_QUALIFIER: Final = "SK"  # LIN04: LIN05 is the buyer's SKU
FREE_FORM: Final = "F"  # PID01
PRODUCT: Final = "08"  # PID02
AVAILABLE: Final = "61"  # QTY01: remaining authorized quantity
DISCONTINUED: Final = "036"  # DTM01: the date replenishment stops
EACH: Final = "EA"
LOOP_ID: Final = "REF"  # LS01 and LE01
DESCRIPTION_WIDTH: Final = 80


@dataclass(frozen=True)
class WarehouseStock:
    """Units available in one warehouse, as the buyer knows it."""

    warehouse: str  # REF02
    quantity: int  # REF03: whole units, never negative


@dataclass(frozen=True)
class InventoryItem:
    """One item and its stock in every warehouse."""

    vendor_sku: str  # LIN03: our item number
    buyer_sku: str  # LIN05: the buyer's SKU
    description: str  # PID05
    stock: tuple[WarehouseStock, ...]
    discontinued_on: date | None = None  # DTM*036


@dataclass(frozen=True)
class InventoryAdvice:
    """A full inventory report: one message states every item we sell the buyer."""

    report_number: str  # BIA03
    created_on: date  # BIA04
    merchant: str  # REF*IO: the buyer's code for itself
    items: tuple[InventoryItem, ...]


def build_body(advice: InventoryAdvice) -> Loop:
    """The body nodes (between ST and SE) for one inventory advice."""
    _check(advice)
    body = Loop(
        "BODY",
        [
            Segment(
                "BIA",
                {
                    "BIA01": ORIGINAL,
                    "BIA02": SELLER_INVENTORY_REPORT,
                    "BIA03": advice.report_number,
                    "BIA04": format_date(advice.created_on),
                },
            ),
            Segment("REF", {"REF01": MERCHANT_QUALIFIER, "REF02": advice.merchant}),
        ],
    )
    body.children += [_item_loop(item) for item in advice.items]
    body.children.append(Segment("CTT", {"CTT01": str(len(advice.items))}))
    return body


def _item_loop(item: InventoryItem) -> Loop:
    loop = Loop(
        "LIN_LOOP",
        [
            Segment(
                "LIN",
                {
                    "LIN02": VENDOR_QUALIFIER,
                    "LIN03": item.vendor_sku,
                    "LIN04": BUYER_QUALIFIER,
                    "LIN05": item.buyer_sku,
                },
            ),
            Loop(
                "PID_LOOP",
                [
                    Segment(
                        "PID",
                        {
                            "PID01": FREE_FORM,
                            "PID02": PRODUCT,
                            "PID05": item.description[:DESCRIPTION_WIDTH],
                        },
                    )
                ],
            ),
        ],
    )
    if item.discontinued_on:
        loop.children.append(
            Segment(
                "DTM",
                {
                    "DTM01": DISCONTINUED,
                    "DTM02": format_date(item.discontinued_on),
                },
            )
        )
    total = sum(stock.quantity for stock in item.stock)
    loop.children.append(
        Segment("QTY", {"QTY01": AVAILABLE, "QTY02": str(total), "QTY03": EACH})
    )
    loop.children.append(
        Loop(
            "LS_LOOP",
            [
                Segment("LS", {"LS01": LOOP_ID}),
                *[
                    Loop(
                        "REF_LOOP",
                        [
                            Segment(
                                "REF",
                                {
                                    "REF01": WAREHOUSE_QUALIFIER,
                                    "REF02": stock.warehouse,
                                    "REF03": str(stock.quantity),
                                },
                            )
                        ],
                    )
                    for stock in item.stock
                ],
                Segment("LE", {"LE01": LOOP_ID}),
            ],
        )
    )
    return loop


def _check(advice: InventoryAdvice) -> None:
    """Refuse an advice that lacks a value the buyer requires."""
    missing = [
        name
        for name, value in (
            ("report_number", advice.report_number),
            ("merchant", advice.merchant),
            ("items", advice.items),
        )
        if not value
    ]
    for item in advice.items:
        missing += [
            name
            for name, value in (
                ("vendor_sku", item.vendor_sku),
                ("buyer_sku", item.buyer_sku),
                ("description", item.description),
                ("stock", item.stock),
            )
            if not value
        ]
        for stock in item.stock:
            if not stock.warehouse:
                missing.append("warehouse")
            if stock.quantity < 0:
                missing.append("non-negative quantity")
    if missing:
        raise ValueError("inventory advice lacks: " + ", ".join(dict.fromkeys(missing)))
