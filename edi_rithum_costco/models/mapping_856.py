"""Outbound 856: the shipment confirmation of a finished Costco delivery."""

import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.base.models.res_company import ResCompany
from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord
from odoo.addons.edi_x12.x12 import outbound
from odoo.addons.sale.models.sale_order import SaleOrder
from odoo.addons.sale.models.sale_order_line import SaleOrderLine
from odoo.addons.stock.models.stock_move_line import StockMoveLine
from odoo.addons.stock.models.stock_picking import StockPicking

from ..documents import tset_856

FUNCTIONAL_ID = "SH"
UNSPECIFIED_METHOD = "UNSP"
TRACKING_SEPARATORS = re.compile(r"[+,;\s]+")
WHOLE_KIT_TOLERANCE = 1e-6


class EdiRithumCostcoMapping856(models.AbstractModel):
    _name = "edi.rithum.costco.mapping.856"
    _description = "Costco 856 Shipment Confirmation"

    @api.model
    def generate(self, exchange_record: EDIExchangeRecord) -> str:
        """The shipment confirmation of the delivery this record is linked to."""
        picking = exchange_record.record
        order = picking.sale_id
        shipped = self._shipped_items(picking)
        confirmation = tset_856.ShipmentConfirmation(
            shipment_id=picking.name,
            po_number=order.client_order_ref or "",
            invoice_number=self._invoice_reference(order),
            shipping_method=self._shipping_method(picking),
            weight=self._weight_in_pounds(picking),
            warehouse=self._warehouse_code(picking),
            shipped_at=self._local(
                picking.company_id, picking.date_done or fields.Datetime.now()
            ),
            created_at=self._local(picking.company_id, fields.Datetime.now()),
            shipped=tuple(shipped),
        )
        body = tset_856.build_body(confirmation)
        envelope = self._envelope(exchange_record, order)
        tree = outbound.interchange(envelope, body, tset_856.TSET, "0001")
        return outbound.render(tree, exchange_record.type_id.x12_map_path())

    def _envelope(
        self, exchange_record: EDIExchangeRecord, order: SaleOrder
    ) -> outbound.Envelope:
        """Addressed to whoever sent the 850 that created the order."""
        origin = order.origin_exchange_record_id
        if not origin.exchange_file:
            raise UserError(
                self.env._(
                    "The order %(name)s was not created from an EDI file.",
                    name=order.name,
                )
            )
        return exchange_record.backend_id.x12_reply_envelope(
            origin._get_file_content(), FUNCTIONAL_ID
        )

    def _invoice_reference(self, order: SaleOrder) -> str:
        """The posted invoice of the order, else the order number."""
        invoices = order.invoice_ids.filtered(
            lambda move: move.move_type == "out_invoice" and move.state == "posted"
        )
        return invoices[:1].name or order.name

    def _shipping_method(self, picking: StockPicking) -> str:
        carrier = picking.carrier_id
        code = carrier.costco_shipping_method
        if not code or code.upper() == UNSPECIFIED_METHOD:
            raise UserError(
                self.env._(
                    "Set a Costco shipping method on the delivery method "
                    "%(carrier)s: Costco needs the code of the carrier and service "
                    "that was used, and does not accept %(unspecified)s.",
                    carrier=carrier.display_name or self.env._("(none)"),
                    unspecified=UNSPECIFIED_METHOD,
                )
            )
        return code

    def _warehouse_code(self, picking: StockPicking) -> str:
        """Our ID of the warehouse the goods shipped from, as Costco knows it."""
        warehouse = picking.picking_type_id.warehouse_id
        if not warehouse.costco_warehouse_code:
            raise UserError(
                self.env._(
                    "Set the Costco warehouse ID on the warehouse %(name)s: Costco "
                    "rejects a shipment confirmation unless it names a warehouse "
                    "already registered for Costco in your Rithum account.",
                    name=warehouse.display_name or self.env._("(none)"),
                )
            )
        return warehouse.costco_warehouse_code

    def _weight_in_pounds(self, picking: StockPicking) -> Decimal:
        weight_uom = self.env[
            "product.template"
        ]._get_weight_uom_id_from_ir_config_parameter()
        pounds = weight_uom._compute_quantity(
            picking.shipping_weight, self.env.ref("uom.product_uom_lb")
        )
        if pounds <= 0:
            raise UserError(
                self.env._(
                    "The delivery %(name)s has no shipping weight.", name=picking.name
                )
            )
        return Decimal(str(pounds))

    def _local(self, company: ResCompany, moment: datetime) -> datetime:
        """``moment`` (naive UTC) in the time zone of ``company``."""
        name = company.partner_id.tz or self.env.user.tz or "UTC"
        return pytz.utc.localize(moment).astimezone(pytz.timezone(name))

    def _shipped_items(self, picking: StockPicking) -> list[tset_856.ShippedItem]:
        """One item per Costco order line shipped, with the boxes it travelled in."""
        lines = picking.move_line_ids.filtered(
            lambda line: line.quantity > 0 and line.move_id.sale_line_id.costco_sku
        )
        if not lines:
            raise UserError(self.env._("No line of the Costco order was shipped."))
        unpacked = lines.filtered(lambda line: not line.result_package_id)
        if unpacked:
            raise UserError(
                self.env._(
                    "Put every shipped item in a package before confirming the "
                    "shipment: %(products)s.",
                    products=", ".join(unpacked.product_id.mapped("display_name")),
                )
            )
        # The carrier labels the delivery's packages in the order of the move lines
        # (the connector builds its packages from the same recordset), and Odoo
        # keeps the tracking numbers in that order: pair them the same way.
        delivery_packages = picking.move_line_ids.result_package_id
        numbers = self._tracking_numbers(picking, delivery_packages)
        tracking = dict(zip(delivery_packages.ids, numbers, strict=True))
        return [
            self._item(sale_line, lines, tracking)
            for sale_line in lines.move_id.sale_line_id
        ]

    def _item(
        self, sale_line: SaleOrderLine, lines: StockMoveLine, tracking: dict[int, str]
    ) -> tset_856.ShippedItem:
        """The units of one order line over all its packages, and their tracking."""
        own = lines.filtered(lambda line: line.move_id.sale_line_id == sale_line)
        quantity = sum(
            (
                self._shipped_quantity(
                    sale_line,
                    own.filtered(lambda line, p=package: line.result_package_id == p),
                    package,
                )
                for package in own.result_package_id
            ),
            Decimal(0),
        )
        return tset_856.ShippedItem(
            line_number=sale_line.edi_id or "",
            vendor_sku=sale_line.product_id.default_code or "",
            buyer_sku=sale_line.costco_sku or "",
            quantity=quantity,
            tracking_numbers=tuple(
                tracking[package.id] for package in own.result_package_id
            ),
        )

    def _tracking_numbers(self, picking: StockPicking, packages) -> list[str]:
        """The carrier's tracking numbers, one per package, in package order."""
        numbers = [
            number
            for number in TRACKING_SEPARATORS.split(picking.carrier_tracking_ref or "")
            if number
        ]
        if len(numbers) != len(packages):
            raise UserError(
                self.env._(
                    "The delivery has %(packages)s package(s) but %(numbers)s "
                    "tracking number(s): Costco needs one for each package.",
                    packages=len(packages),
                    numbers=len(numbers),
                )
            )
        return numbers

    def _shipped_quantity(
        self, sale_line: SaleOrderLine, lines: StockMoveLine, package
    ) -> Decimal:
        """Units of the ordered product in this package; kits count whole kits."""
        bom = sale_line.move_ids.bom_line_id.bom_id.filtered(
            lambda b: b.type == "phantom"
        )[:1]
        if not bom:
            return Decimal(
                str(
                    sum(
                        line.product_uom_id._compute_quantity(
                            line.quantity, sale_line.product_uom_id
                        )
                        for line in lines
                    )
                )
            )
        return self._kits_in(bom, sale_line, lines, package)

    def _kits_in(
        self, bom, sale_line: SaleOrderLine, lines: StockMoveLine, package
    ) -> Decimal:
        """How many whole kits the components in this package make up."""
        ratios = self._components_per_kit(bom, sale_line.product_id)
        if set(lines.product_id) - set(ratios):
            raise self._partial_kit(sale_line, package)
        counts = {
            product: sum(
                line.quantity_product_uom
                for line in lines
                if line.product_id == product
            )
            / ratio
            for product, ratio in ratios.items()
        }
        kits = min(counts.values())
        whole = round(kits)
        if whole <= 0 or any(
            abs(c - whole) > WHOLE_KIT_TOLERANCE for c in counts.values()
        ):
            raise self._partial_kit(sale_line, package)
        return Decimal(whole)

    def _components_per_kit(self, bom, product) -> dict:
        """Component product -> quantity (in its own unit) that one kit holds."""
        __, lines_done = bom.explode(product, 1.0)
        ratios = defaultdict(float)
        for bom_line, values in lines_done:
            ratios[bom_line.product_id] += bom_line.product_uom_id._compute_quantity(
                values["qty"], bom_line.product_id.uom_id
            )
        return ratios

    def _partial_kit(self, sale_line: SaleOrderLine, package) -> UserError:
        return UserError(
            self.env._(
                "The components of %(kit)s in package %(package)s do not make "
                "whole kits.",
                kit=sale_line.product_id.display_name,
                package=package.display_name,
            )
        )
