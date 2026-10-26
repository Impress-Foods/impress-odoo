from odoo import Command, api, fields, models

from odoo.addons.product.models.product_product import ProductProduct
from odoo.addons.quality.models.quality import QualityCheck
from odoo.addons.stock.models.stock_lot import StockLot
from odoo.addons.stock.models.stock_picking import StockPicking


class QualityAlert(models.Model):
    _inherit = "quality.alert"

    alert_type = fields.Selection(
        selection=[("quality", "Quality"), ("salubrity", "Salubrity")],
        default="quality",
        tracking=True,
    )

    quantity = fields.Float(
        digits="Product Unit of Measure",
        tracking=True,
    )

    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        compute="_compute_product_uom_id",
        store=True,
        readonly=False,
    )

    contacted_person = fields.Char(
        string="Person Contacted",
    )

    impact_on_product = fields.Selection(
        selection=[("no", "No"), ("yes", "Yes")],
        string="Impact on Product",
        tracking=True,
        default="no",
    )

    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Purchase Order",
        compute="_compute_origin_orders",
        store=True,
        readonly=False,
        check_company=True,
        tracking=True,
    )

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sales Order",
        compute="_compute_origin_orders",
        store=True,
        readonly=False,
        check_company=True,
        tracking=True,
    )

    vendor_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        related="purchase_order_id.partner_id",
        store=True,
    )

    customer_id = fields.Many2one(
        "res.partner",
        string="Customer",
        related="sale_order_id.partner_id",
        store=True,
    )

    signature = fields.Binary()

    follow_up = fields.Html()

    @api.model_create_multi
    def create(self, vals_list):
        """Link the product and lots of the origin before creating the alert."""
        for values in vals_list:
            self._fill_origin_product(values)
        return super().create(vals_list)

    @api.model
    def _get_check_from_values(self, values: dict) -> QualityCheck:
        if values.get("check_id"):
            return self.env["quality.check"].browse(values["check_id"])
        return self.env["quality.check"]

    @api.model
    def _get_picking_from_values(self, values: dict) -> StockPicking:
        picking = self.env["stock.picking"]
        if values.get("picking_id"):
            picking = picking.browse(values["picking_id"])
        return picking or self._get_check_from_values(values).picking_id

    @api.model
    def _get_product_from_values(self, values: dict) -> ProductProduct:
        product = self.env["product.product"]
        if values.get("product_id"):
            return product.browse(values["product_id"])
        if values.get("product_tmpl_id"):
            template = self.env["product.template"].browse(values["product_tmpl_id"])
            if len(template.product_variant_ids) == 1:
                return template.product_variant_ids
            return product
        check = self._get_check_from_values(values)
        if check.product_id:
            return check.product_id
        picking = self._get_picking_from_values(values)
        if picking:
            picking_products = picking.move_ids.product_id
            if len(picking_products) == 1:
                return picking_products
        order_products = product
        if values.get("purchase_order_id"):
            order_products |= (
                self.env["purchase.order"]
                .browse(values["purchase_order_id"])
                .order_line.product_id
            )
        if values.get("sale_order_id"):
            order_products |= (
                self.env["sale.order"]
                .browse(values["sale_order_id"])
                .order_line.product_id
            )
        if len(order_products) == 1:
            return order_products
        return product

    @api.model
    def _get_lots_from_values(self, values: dict, product: ProductProduct) -> StockLot:
        lots = self.env["stock.lot"]
        check = self._get_check_from_values(values)
        if check.lot_ids:
            lots = check.lot_ids
        if not lots:
            picking = self._get_picking_from_values(values)
            if picking:
                lots = (
                    picking.move_line_ids.lot_id | picking.move_ids.move_line_ids.lot_id
                )
        if product:
            lots = lots.filtered(lambda lot: lot.product_id == product)
        return lots

    @api.model
    def _fill_origin_product(self, values: dict) -> None:
        """Complete the values with the product and lots of the origin.

        Only fields that were not explicitly provided are filled, so a product
        chosen by the user always wins over the detected one.
        """
        product = self._get_product_from_values(values)
        if not product:
            return
        if not values.get("product_id"):
            values["product_id"] = product.id
        if not values.get("product_tmpl_id"):
            values["product_tmpl_id"] = product.product_tmpl_id.id
        if not values.get("lot_ids"):
            lots = self._get_lots_from_values(values, product)
            if lots:
                values["lot_ids"] = [Command.set(lots.ids)]

    @api.onchange("check_id", "picking_id", "purchase_order_id", "sale_order_id")
    def _onchange_origin_product(self) -> None:
        for alert in self:
            values = {
                "product_id": alert.product_id.id,
                "product_tmpl_id": alert.product_tmpl_id.id,
                "check_id": alert.check_id.id,
                "picking_id": alert.picking_id.id,
                "purchase_order_id": alert.purchase_order_id.id,
                "sale_order_id": alert.sale_order_id.id,
            }
            product = self._get_product_from_values(values)
            if not alert.product_id and product:
                alert.product_tmpl_id = product.product_tmpl_id
                alert.product_id = product
            if not alert.lot_ids:
                lots = self._get_lots_from_values(values, product or alert.product_id)
                if lots:
                    alert.lot_ids = [Command.set(lots.ids)]

    @api.depends("product_id")
    def _compute_product_uom_id(self) -> None:
        for alert in self:
            alert.product_uom_id = alert.product_id.uom_id

    @api.depends(
        "picking_id.move_ids.purchase_line_id.order_id",
        "picking_id.move_ids.sale_line_id.order_id",
        "check_id.picking_id",
        "check_id.move_id.purchase_line_id.order_id",
        "check_id.move_id.sale_line_id.order_id",
        "check_id.move_line_id.move_id.purchase_line_id.order_id",
        "check_id.move_line_id.move_id.sale_line_id.order_id",
    )
    def _compute_origin_orders(self) -> None:
        """Prefill the orders from the transfer or the check, when there is one.

        The fields stay editable: a transfer can carry several orders, and the
        first one found is only a reasonable default.
        """
        for alert in self:
            picking = alert.picking_id or alert.check_id.picking_id
            moves = (
                picking.move_ids
                | alert.check_id.move_id
                | alert.check_id.move_line_id.move_id
            )
            alert.purchase_order_id = (
                picking.purchase_id or moves.purchase_line_id.order_id[:1]
            )
            alert.sale_order_id = picking.sale_id or moves.sale_line_id.order_id[:1]

    def action_view_purchase_order(self) -> dict:
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Purchase Order"),
            "res_model": "purchase.order",
            "views": [(False, "form")],
            "res_id": self.purchase_order_id.id,
        }

    def action_view_sale_order(self) -> dict:
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Sales Order"),
            "res_model": "sale.order",
            "views": [(False, "form")],
            "res_id": self.sale_order_id.id,
        }
