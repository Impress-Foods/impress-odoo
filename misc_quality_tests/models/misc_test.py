from typing_extensions import Self

from odoo import _, api, fields, models


class MiscTest(models.Model):
    _name = "misc.test"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Test"
    _rec_name = "sequence"
    _order = "sequence"
    sequence = fields.Char()

    product_id = fields.Many2one("product.template")
    lot_id = fields.Many2one("stock.lot")
    affected_product_ids = fields.Many2many(
        "product.template", string="Affected Product(s)"
    )
    affected_product_count = fields.Integer(compute="_compute_affected_product_count")
    description = fields.Html()
    date = fields.Date()

    @api.depends("affected_product_ids")
    def _compute_affected_product_count(self) -> None:
        for test in self:
            test.affected_product_count = len(test.affected_product_ids)

    @api.model_create_multi
    def create(self, vals_list) -> Self:
        for vals in vals_list:
            if "sequence" not in vals or not vals["sequence"]:
                vals["sequence"] = self.env["ir.sequence"].next_by_code("misc.test")
        return super().create(vals_list)

    def action_open_affected_products(self) -> dict:
        self.ensure_one()
        if self.affected_product_count == 1:
            action = {
                "name": _("Products"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "product.template",
                "res_id": self.affected_product_ids[0].id,
            }
        else:
            action = {
                "name": _("Products"),
                "type": "ir.actions.act_window",
                "view_mode": "tree,form",
                "res_model": "product.template",
                "domain": [("id", "in", self.affected_product_ids.ids)],
            }

        return action
