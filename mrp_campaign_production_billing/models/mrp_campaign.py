from odoo import fields, models


class MrpCampaignProductionBilling(models.Model):
    _name = "mrp.campaign"
    _inherit = "mrp.campaign"

    workflow_type = fields.Selection(
        selection_add=[("production_billing", "Production Billing")]
    )
