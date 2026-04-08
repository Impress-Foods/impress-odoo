import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    invoice_partner_id = fields.Many2one("res.partner")

    def get_invoicing_partner(self):
        if self.invoice_partner_id:
            return self.invoice_partner_id.id
        else:
            return self.id
