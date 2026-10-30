from odoo import models


class EdiRithumCostcoIntake(models.AbstractModel):
    _name = "edi.rithum.costco.intake"
    _inherit = "edi.rithum.intake"
    _description = "Costco intake"

    # The documents Costco sends that we read. Its 997s are read by edi_rithum.
    ROUTES = {("PO", "850"): "edi.rithum.costco.mapping.850"}
