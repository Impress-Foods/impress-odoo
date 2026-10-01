from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class LabelWizard(models.TransientModel):
    _name = "label.wizard"
    _description = "Label Wizard"

    model = fields.Selection(
        [
            ("product.product", "Product"),
            ("stock.lot", "Lot"),
        ],
        default="product.product",
        required=True,
    )

    product_id = fields.Many2one("product.product")

    uom_id = fields.Many2one("uom.uom", related="product_id.uom_id")
    lot_id = fields.Many2one("stock.lot")

    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Packaging",
        domain="[('id', 'in', available_uom_ids)]",
        compute="_compute_product_uom_id",
        inverse="_inverse_product_uom_id",
        store=True,
        readonly=False,
    )

    available_uom_ids = fields.Many2many(
        "uom.uom",
        string="Available UOMs",
        compute="_compute_available_uom_ids",
    )

    picking_id = fields.Many2one("stock.picking")

    product_uom_qty = fields.Float(string="Quantity")

    label_qty = fields.Integer(default=1, string="Number of Labels")

    label_report = fields.Many2one("ir.actions.report", compute="_compute_label_report")

    label_size = fields.Selection(
        [
            ("2x4", "2x4"),
            ("4x6", "4x6"),
        ],
        default="2x4",
        required=True,
    )

    @api.constrains("label_qty")
    def _check_label_qty(self):
        for record in self:
            if record.label_qty <= 0:
                raise ValidationError(self.env._("Must print at least 1 label!"))

    @api.constrains("product_uom_qty")
    def _check_product_uom_qty(self):
        for record in self:
            if record.product_uom_qty < 0:
                raise ValidationError(self.env._("Must set a 0 or positive quantity!"))

    # ------------------------------------------------------------------
    # Autofill helpers
    # ------------------------------------------------------------------
    @api.model
    def _quantity_and_uom_for(self, picking, product, lot):
        """Return (qty, uom) for the given picking/product/lot triple.

        Pure helper used by default_get and the onchange, so both paths
        stay in sync. No side effects.
        """
        if not picking or not picking.exists() or not product or not product.exists():
            return 0, False

        quantity = 0
        selected_uom = False
        if product.tracking in ["lot", "serial"] and lot and lot.exists():
            move_lines = picking.move_line_ids.filtered(
                lambda ml, product=product, lot=lot: (
                    ml.product_id == product and ml.lot_id == lot
                )
            )
            quantity = sum(move_lines.mapped("quantity"))
            if move_lines:
                selected_uom = move_lines[0].product_uom_id
        else:
            moves = picking.move_ids.filtered(
                lambda m, product=product: m.product_id == product
            )
            quantity = sum(moves.mapped("product_uom_qty"))
            if moves:
                selected_uom = moves[0].product_uom

        return quantity, selected_uom

    @api.model
    def default_get(self, fields):
        vals = super().default_get(fields)

        if "model" in fields and not vals.get("model") and vals.get("lot_id"):
            vals["model"] = "stock.lot"

        if (
            vals.get("picking_id")
            and vals.get("product_id")
            and ("product_uom_qty" in fields or "product_uom_id" in fields)
        ):
            picking = self.env["stock.picking"].browse(vals["picking_id"])
            product = self.env["product.product"].browse(vals["product_id"])
            lot_id = vals.get("lot_id")
            lot = (
                self.env["stock.lot"].browse(lot_id)
                if lot_id
                else self.env["stock.lot"]
            )

            qty, uom = self._quantity_and_uom_for(picking, product, lot)

            if "product_uom_qty" in fields and qty and not vals.get("product_uom_qty"):
                vals["product_uom_qty"] = qty

            if "product_uom_id" in fields and uom and not vals.get("product_uom_id"):
                product_uoms = product.uom_id | product.product_uom_ids.uom_id
                product_uoms |= product.uom_ids
                if uom in product_uoms:
                    vals["product_uom_id"] = uom.id

        return vals

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("model", "label_size")
    def _compute_label_report(self) -> None:
        for record in self:
            report_ref = False
            if record.model == "product.product":
                if record.label_size == "2x4":
                    report_ref = (
                        "label_printing_wizard.report_label_product_product_zpl_2x4"
                    )
                else:
                    report_ref = (
                        "label_printing_wizard.report_label_product_product_zpl_4x6"
                    )
            elif record.model == "stock.lot":
                if record.label_size == "2x4":
                    report_ref = "label_printing_wizard.report_label_lot_zpl_2x4"
                else:
                    report_ref = "label_printing_wizard.report_label_lot_zpl_4x6"

            record.label_report = self.env.ref(report_ref) if report_ref else False

    @api.depends("product_id")
    def _compute_available_uom_ids(self):
        for record in self:
            if not record.product_id:
                record.available_uom_ids = False
                continue
            product = record.product_id
            uoms = product.uom_id | product.product_uom_ids.uom_id
            uoms |= product.uom_ids
            record.available_uom_ids = uoms

    @api.depends("product_id")
    def _compute_product_uom_id(self):
        for rec in self:
            rec.product_uom_id = rec.product_id.uom_id if rec.product_id else False

    def _inverse_product_uom_id(self):
        return

    @api.onchange("picking_id", "product_id", "lot_id")
    def get_product_uom_qty(self) -> None:
        for record in self:
            if not record.picking_id or not record.product_id:
                continue

            quantity, selected_uom = self._quantity_and_uom_for(
                record.picking_id, record.product_id, record.lot_id
            )

            record.product_uom_qty = quantity
            if selected_uom and selected_uom in record.available_uom_ids:
                record.product_uom_id = selected_uom

    def _make_values(self) -> dict:
        self.ensure_one()
        res_id = 0
        match self.model:
            case "product.product":
                res_id = self.product_id.id
            case "stock.lot":
                res_id = self.lot_id.id
            case _:
                raise ValidationError(self.env._("Invalid model for wizard!"))

        data = {
            "label_count": self.label_qty,
            "product_uom_qty": self.product_uom_qty,
            "product_uom_id": self.product_uom_id.id,
        }

        return {str(res_id): data}

    def print_label(self):
        self.ensure_one()

        report = self.label_report
        if not report:
            raise UserError(self.env._("Report type not supported"))
        data = self._make_values()

        # report_action expects int docids; keys are str for JSON round-trip
        docids = [int(k) for k in data]
        return report.report_action(docids, data)
