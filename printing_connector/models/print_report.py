from odoo import fields, models


class PrintReport(models.Model):
    _name = "print.report"
    _description = "Report for label printing"

    name = fields.Char()

    mapping_ids = fields.One2many("print.field", "report_id")
    target_model_id = fields.Many2one("ir.model")

    def _render_json_payload(self, rec):
        self.ensure_one()
        rec.ensure_one()

        data = {
            field.target_field: field.get_formatted_value(rec)
            for field in self.mapping_ids
        }
        return data
