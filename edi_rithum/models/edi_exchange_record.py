from odoo import fields, models


class EdiExchangeRecord(models.Model):
    _inherit = "edi.exchange.record"

    rithum_partner_id = fields.Many2one(
        "edi.rithum.partner",
        string="Rithum partner",
        index=True,
        copy=False,
        readonly=True,
        help="The retailer whose interchange ID the file came from.",
    )
