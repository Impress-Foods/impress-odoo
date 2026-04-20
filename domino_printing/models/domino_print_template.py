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
    work_center_ids = fields.Many2many(
        "mrp.workcenter",
        string="Work Centers",
        related="domino_label_id.workcenter_ids",
    )

    field_ids = fields.Many2many(
        "domino.print.field",
        string="Field Mappings",
    )

    def _make_json_payload(self, target: QualityCheck) -> dict:
        self.ensure_one()
        fields = {}
        data_fields = []
        for field in self.field_ids:
            if field.field_type == "data":
                data_fields.append(field.get_field_value(target))
            else:
                fields[field.target_field] = field.get_field_value(target)

        self._validate_payload(fields)
        payload = {"textFields": fields, "dataFields": data_fields}
        return payload

    def _validate_payload(self, payload: dict):
        self.ensure_one()
        required_fields = self.field_ids.filtered("required")

        for field in required_fields:
            if field.target_field not in payload:
                raise ValidationError(
                    self.env._(
                        "Could not find required field %(field)s in print payload",
                        field=field.target_field,
                    )
                )
