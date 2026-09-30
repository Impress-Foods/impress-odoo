from typing import Any

from odoo import fields, models


class PrintReport(models.Model):
    _name = "print.report"
    _description = "API payload profile"
    _order = "name"

    name = fields.Char(required=True)
    target_model_id = fields.Many2one("ir.model", required=True, ondelete="cascade")
    model = fields.Char(related="target_model_id.model", store=True)
    template = fields.Char(required=True)
    mapping_ids = fields.One2many(
        comodel_name="print.field",
        inverse_name="report_id",
        string="Field Mappings",
    )

    def _get_record_data(
        self, data: dict[str, Any] | None, record: models.Model
    ) -> dict[str, Any]:
        """Extract per-record data while retaining global action options."""
        if not isinstance(data, dict):
            return {}

        record_data = data.get(str(record.id), data.get(record.id))
        if not isinstance(record_data, dict):
            return data

        global_data = {
            key: value for key, value in data.items() if not str(key).isdigit()
        }
        return global_data | record_data

    def _render_json_payloads(
        self, records: models.Model, data: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        self.ensure_one()
        return [
            {
                "record_id": record.id,
                "values": self._render_json_payload(
                    record,
                    extra_data=self._get_record_data(data, record),
                ),
            }
            for record in records
        ]

    def _render_json_payload(
        self, record: models.Model, extra_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.ensure_one()
        record.ensure_one()
        payload = dict(extra_data or {})
        if "_qty" not in payload:
            payload["_qty"] = 1
        for mapping in self.mapping_ids:
            if mapping.translate:
                for language in mapping.languages:
                    key = f"{mapping.target_field}_{language.code[:2]}"
                    payload[key] = mapping.get_formatted_value(
                        record.with_context(lang=language.code)
                    )
            else:
                payload[mapping.target_field] = mapping.get_formatted_value(record)
        return payload
