import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    billing_sale_order_id = fields.Many2one(
        "sale.order",
        string="Billing Sale Order",
        compute="_compute_billing_sale_order_id",
        store=True,
    )
    billing_sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="Billing Sale Order Line",
        compute="_compute_billing_sale_order_line_id",
        store=True,
    )
    billing_sale_order_ref = fields.Char(
        string="Billing Sale Order Reference", store=True
    )
    billing_partner_id = fields.Many2one(
        "res.partner",
        related="billing_sale_order_id.partner_id",
        store=True,
    )

    invoice_status = fields.Boolean()

    @api.depends("billing_sale_order_ref")
    def _compute_billing_sale_order_id(self):
        for rec in self:
            if rec.billing_sale_order_ref:
                value = self.env["sale.order"].search(
                    [("client_order_ref", "=", rec.billing_sale_order_ref)], limit=1
                )

                if not value:
                    raise ValidationError(
                        self.env._(
                            "No Sale Order found with"
                            f"reference {rec.billing_sale_order_ref}"
                        )
                    )
                else:
                    rec.billing_sale_order_id = value
            else:
                rec.billing_sale_order_id = None

    @api.depends("billing_sale_order_id")
    def _compute_billing_sale_order_line_id(self):
        for rec in self:
            # There is a billing SO, we must update the SOL or create it
            if rec.billing_sale_order_id:
                # There is a SOL and it belongs to the same SO, we must update it.
                if (
                    rec.billing_sale_order_line_id
                    and rec.billing_sale_order_line_id.order_id
                    == rec.billing_sale_order_id
                ):
                    rec._recompute_billing_line_qty()

                # There is a SOL and it belongs to a different SO, we must unlink it
                elif (
                    rec.billing_sale_order_line_id
                    and rec.billing_sale_order_line_id.order_id
                    != rec.billing_sale_order_id
                ):
                    rec._unlink_sale_order_line()

                # No SOL, we must link it
                if not rec.billing_sale_order_line_id:
                    sale_order_line_dict = {
                        product: sale_order_line
                        for (product, sale_order_line) in zip(
                            rec.billing_sale_order_id.order_line.mapped("product_id"),
                            rec.billing_sale_order_id.order_line,
                            strict=False,
                        )
                    }

                    billing_product = self.bom_id.get_production_billing_product()

                    if billing_product in sale_order_line_dict:
                        rec.billing_sale_order_line_id = sale_order_line_dict[
                            billing_product
                        ]
                        rec._recompute_billing_line_qty()
                    else:
                        raise ValidationError(
                            self.env._(
                                "No Sale Order Line found in SO. Expected "
                                f"line with product {billing_product.display_name}"
                            )
                        )

            # No Billing sale order, we must unlink the MO from the SOL
            elif not rec.billing_sale_order_id:
                if rec.billing_sale_order_line_id:
                    rec._unlink_sale_order_line()

    def _create_billing_sale_order_line(self):
        new_order_line = self.env["sale.order.line"].create(
            {
                "order_id": self.billing_sale_order_id.id,
                "product_id": self.bom_id.get_production_billing_product().id,
                "product_uom_qty": self.product_uom_qty,
            }
        )
        self.billing_sale_order_line_id = new_order_line
        self._recompute_billing_line_qty()

    def _unlink_sale_order_line(self):
        if (
            self.env["mrp.production"].search(
                [
                    (
                        "billing_sale_order_line_id",
                        "=",
                        self.billing_sale_order_line_id.id,
                    )
                ]
            )
            != self
        ):
            self._recompute_billing_line_qty()
            self.billing_sale_order_line_id = None
        else:
            self._recompute_billing_line_qty()
            if self.billing_sale_order_line_id.order_id.state == "draft":
                self.billing_sale_order_line_id.unlink()

    def _recompute_billing_line_qty(self):
        # Optional feature, used to compute the total qty to deliver
        # based on the MOs linked to the SOL.
        if self.billing_sale_order_line_id and self.env.context.get(
            "compute_mo_billing_qty"
        ):
            shared_order_line_production = self.env["mrp.production"].search(
                [
                    (
                        "billing_sale_order_line_id",
                        "=",
                        self.billing_sale_order_line_id.id,
                    ),
                    ("state", "not in", ["cancel"]),
                ]
            )
            total_qty_to_deliver = sum(
                shared_order_line_production.mapped("product_uom_qty")
            )
            self.billing_sale_order_line_id.product_uom_qty = total_qty_to_deliver

    def button_mark_done(self):
        res = super().button_mark_done()
        self.update_billing_sale_order_line_on_done()
        return res

    def update_billing_sale_order_line_on_done(self):
        self.ensure_one()
        if self.billing_sale_order_line_id:
            self.billing_sale_order_line_id.qty_delivered += self.qty_produced

    def _action_cancel(self):
        res = super()._action_cancel()
        if self.billing_sale_order_id:
            self.billing_sale_order_id = None
            self.billing_sale_order_ref = False
        return res

    def write(self, vals):
        res = super().write(vals)
        if bool(
            set(["product_qty", "qty_produced", "qty_producing"]).intersection(vals)
        ):
            self._recompute_billing_line_qty()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        # Fixes the import bug while still preserving the functionality.
        # A procurement group still gets created on import.
        for vals in vals_list:
            # Guard to only applys the fix when creating a
            #  MO with a billing SO reference.
            # This only should happen on import, BOs and splits
            if "billing_sale_order_ref" in vals:
                vals.pop("procurement_group_id", None)
        return super().create(vals_list)

    def get_portal_url(self):
        self.ensure_one()
        return f"/my/manufacturings/{self.id}"
