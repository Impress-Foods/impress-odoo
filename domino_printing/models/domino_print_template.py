import logging

from odoo import fields, models
from odoo.exceptions import ValidationError

from odoo.addons.quality.models.quality import QualityCheck

_logger = logging.getLogger(__name__)


class DominoPrintTemplate(models.Model):
    _name = "domino.print.template"
    _description = "Domino Print Template"
    _order = "name"

    name = fields.Char(required=True)

    print_type = fields.Selection(
        [("code", "Code"), ("case", "Case")],
        required=True,
        help="Code = unit label, Case = box label",
    )
    domino_label_id = fields.Many2one(
        "domino.label",
        string="Domino Label",
        required=True,
    )

    field_ids = fields.Many2many(
        "domino.print.field",
        string="Field Mappings",
    )

    def _make_json_payload(self, target: QualityCheck) -> dict:
        self.ensure_one()
        fields_dict = {}
        data_fields = []
        for field in self.field_ids:
            if field.field_type == "data":
                data_fields.append(field.get_field_value(target))
            else:
                fields_dict[field.target_field] = field.get_field_value(target)

        self._validate_payload(fields_dict, data_fields)
        return {"textFields": fields_dict, "dataFields": data_fields}

    def _validate_payload(self, fields: dict, data_fields: list):
        self.ensure_one()
        required_fields = self.field_ids.filtered("required")

        for field in required_fields:
            if field.field_type == "data":
                matched = any(d.get("name") == field.target_field for d in data_fields)
            else:
                matched = field.target_field in fields
            if not matched:
                raise ValidationError(
                    self.env._(
                        "Could not find required field %(field)s in print payload",
                        field=field.target_field,
                    )
                )
