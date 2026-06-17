from odoo import fields, models
from odoo.fields import Domain


class ResPartner(models.Model):
    _inherit = "res.partner"

    obibox_coverage = fields.Boolean(default=False)
    obibox_coverage_checked = fields.Boolean(default=False)

    def _get_obibox_coverage(self):
        carrier = self.env.ref(
            "delivery_obibox.delivery_carrier_obibox", raise_if_not_found=False
        )
        if not carrier:
            carrier = self.env["delivery.carrier"].search(
                Domain("delivery_type", "=", "obibox"), limit=1
            )

        if not carrier:
            self.obibox_coverage = False
            return
        provider = carrier._get_provider()
        for rec in self:
            if rec.zip:
                rec.obibox_coverage_checked = True
                rec.obibox_coverage = provider.check_coverage(rec)
            else:
                rec.obibox_coverage = False

    def write(self, vals):
        res = super().write(vals)
        if "zip" in vals:
            self.obibox_coverage_checked = False
        return res
