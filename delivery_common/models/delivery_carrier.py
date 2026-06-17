from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    confirmation_template_id = fields.Many2one("mail.template")
    send_confirmation_email = fields.Boolean()

    def _get_provider(self):
        self.ensure_one()
        return None
