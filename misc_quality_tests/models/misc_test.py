from typing_extensions import Self

from odoo import api, fields, models


class MiscTest(models.Model):
    _name = "misc.test"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Misc. Test for products and lots"
    _rec_name = "sequence"
    _order = "sequence"
    sequence = fields.Char()

    product_id = fields.Many2one("product.template")
    lot_id = fields.Many2one("stock.lot")
    affected_product_ids = fields.Many2many(
        "product.template", string="Affected Product(s)"
    )
    description = fields.Html()
    date = fields.Date()

    @api.model_create_multi
    def create(self, vals_list) -> Self:
        for vals in vals_list:
            if "sequence" not in vals or not vals["sequence"]:
                vals["sequence"] = self.env["ir.sequence"].next_by_code("misc.test")
        return super().create(vals_list)
