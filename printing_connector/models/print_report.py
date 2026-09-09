import logging

from odoo import fields, models
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class PrintReport(models.Model):
    _name = "print.report"
    _description = "Report for label printing"

    name = fields.Char(required=True)
    mapping_ids = fields.One2many("print.field", "report_id")
    target_model_id = fields.Many2one("ir.model")
    model = fields.Char(related="target_model_id.model")
    print_server_id = fields.Many2one("print.server")
    template = fields.Char(required=True)

    def _render_json_payload(self, rec, extra_data=None):
        self.ensure_one()
        rec.ensure_one()

        data = {
            field.target_field: field.get_formatted_value(rec)
            for field in self.mapping_ids.filtered_domain(
                Domain("translate", "=", False)
            )
        }

        for field in self.mapping_ids.filtered_domain(Domain("translate", "=", True)):
            for lang in field.languages:
                key = f"{field.target_field}_{lang.code[:2]}"
                data[key] = field.get_formatted_value(rec.with_context(lang=lang.code))

        if extra_data:
            data = extra_data | data
        return data
