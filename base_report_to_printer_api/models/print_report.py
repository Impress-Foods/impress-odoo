from typing import Any

from odoo import api, fields, models


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

    @api.constrains("target_model_id")
    def _check_mapping_fields(self):
        """Revalidate the mappings when a profile is pointed at another model."""
        for profile in self:
            for mapping in profile.mapping_ids:
                mapping._resolve_source_field()

    def _get_record_data(
        self, data: dict[str, Any] | None, record: models.Model
    ) -> dict[str, Any]:
        """Return the part of ``data`` that belongs to ``record``.

        ``data`` carries two kinds of key.  A key that spells a record id holds
        the options for that one record, because a multi-record job sends one
        request per record and each may need its own count.  Every other key is
        an option for the job as a whole.

        Only the global keys and this record's own entry reach the payload.
        The other records' entries must not: they are keyed by an id the remote
        server has no meaning for, so they would ship as literal fields on
        somebody else's label.
        """
        if not isinstance(data, dict):
            return {}

        global_data = {
            key: value for key, value in data.items() if not str(key).isdigit()
        }
        record_data = data.get(str(record.id), data.get(record.id))
        if not isinstance(record_data, dict):
            return global_data

        return global_data | record_data

    def _render_json_payload(
        self, record: models.Model, extra_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.ensure_one()
        record.ensure_one()
        payload = dict(extra_data or {})
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
