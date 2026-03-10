import logging

from odoo import _, api, fields, models
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
    billing_product_id = fields.Many2one(related="bom_id.billing_product_id")

    invoice_status = fields.Boolean()

    @api.constrains("billing_sale_order_line_id", "product_id", "bom_id")
    def _check_billing_sale_order_line_id(self):
        for rec in self:
            if (
                rec.billing_sale_order_ref
                and rec.billing_sale_order_line_id.product_id != rec.billing_product_id
            ):
                raise ValidationError(
                    _(
                        "Billing product %(bill)s does not match "
                        "Sale Order Line product %(so)s"
                        % {
                            "bill": rec.billing_product_id.display_name,
                            "so": (
                                rec.billing_sale_order_line_id.product_id.display_name
                            ),
                        }
                    )
                )

    @api.constrains("billing_sale_order_id")
    def _check_billing_sale_order_id(self):
        for rec in self:
            valid_lines = rec.billing_sale_order_id.order_line.filtered_domain(
                [("product_id", "=", rec.billing_product_id.id)]
            )
            if len(valid_lines) > 1:
                raise ValidationError(
                    _(
                        "Multiple lines in SO with product %s"
                        % rec.billing_product_id.display_name
                    )
                )

    @api.depends("billing_sale_order_ref")
    def _compute_billing_sale_order_id(self):
        for rec in self:
            if rec.billing_sale_order_ref:
                value = self.env["sale.order"].search(
                    [("client_order_ref", "=", rec.billing_sale_order_ref)]
                )

                if len(value) > 1:
                    raise ValidationError(
                        _(
                            "Multiple Sale Orders with reference %(ref)s."
                            % {"ref": rec.billing_sale_order_ref}
                        )
                    )

                if not value:
                    raise ValidationError(
                        _(
                            "No Sale Order found with reference %(ref)s."
                            % {"ref": rec.billing_sale_order_ref}
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
                # There is a SOL and it belongs to a different SO, we must unlink it
                if (
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

                    billing_product = rec.billing_product_id

                    if billing_product in sale_order_line_dict:
                        rec.billing_sale_order_line_id = sale_order_line_dict[
                            billing_product
                        ]
                    else:
                        raise ValidationError(
                            _(
                                "No Sale Order Line found in SO. Expected "
                                f"line with product {billing_product.display_name}"
                            )
                        )

            # No Billing sale order, we must unlink the MO from the SOL
            elif not rec.billing_sale_order_id:
                if rec.billing_sale_order_line_id:
                    rec._unlink_sale_order_line()

    def _create_billing_sale_order_line(self):
        self.ensure_one()
        new_order_line = self.env["sale.order.line"].create(
            {
                "order_id": self.billing_sale_order_id.id,
                "product_id": self.bom_id.billing_product_id.id,
                "product_uom_qty": self.product_uom_qty,
            }
        )
        self.billing_sale_order_line_id = new_order_line

    def _unlink_sale_order_line(self):
        # TODO: Can we just leave the line there?
        self.ensure_one()
        if len(self.billing_sale_order_line_id.production_ids) > 1:
            self.billing_sale_order_line_id = None
        else:
            if self.billing_sale_order_line_id.order_id.state == "draft":
                self.billing_sale_order_line_id.unlink()

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
