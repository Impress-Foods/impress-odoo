from odoo import fields, models


class QualityControlPoint(models.Model):
    _inherit = "quality.point"

    test_report_type = fields.Selection(
        selection_add=[("api", "API")], ondelete={"api": "set default"}
    )

    report_id = fields.Many2one(
        "ir.actions.report",
        domain=[("model", "=", "quality.check"), ("report_type", "=", "api")],
    )

    printer_id = fields.Many2one("print.printer")
