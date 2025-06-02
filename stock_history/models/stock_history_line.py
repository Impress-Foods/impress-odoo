import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class Stock_history_line(models.Model):
    _name = "stock.history.line"
    _description = "Stock History Line"
    _rec_name = "sequence"

    _sql_constraints = [
        (
            "unique_sequence_number",
            "UNIQUE(sequence)",
            "Sequence Number must be unique!",
        ),
    ]
    sequence = fields.Char(default=lambda self: _("New"), copy=False)

    product_id = fields.Many2one("product.product")
    quantity = fields.Float()
    uom = fields.Many2one("uom.uom")

    date = fields.Datetime()
    location = fields.Many2one("stock.location")

    history_group_id = fields.Many2one("stock.history.group")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "sequence" not in vals or vals["sequence"] == _("New"):
                vals["sequence"] = self.env["ir.sequence"].next_by_code(
                    "stock_history_line"
                ) or _("New")
        return super().create(vals_list)
