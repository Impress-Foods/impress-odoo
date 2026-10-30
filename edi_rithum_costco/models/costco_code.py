from odoo import fields, models


class EdiRithumCostcoCode(models.Model):
    """A code Costco defines for an element of our messages (Rithum's code list)."""

    _name = "edi.rithum.costco.code"
    _description = "Costco Message Code"
    _order = "code_type, name"
    _rec_name = "name"

    code_type = fields.Selection(
        [("cancel_reason", "Cancel reason")],
        required=True,
        index=True,
    )
    code = fields.Char(required=True, help="The value sent in the message.")
    name = fields.Char(string="Description", required=True, translate=True)

    _code_unique = models.Constraint(
        "UNIQUE(code_type, code)", "A code can appear only once per type."
    )
