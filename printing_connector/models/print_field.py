import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FieldMapping(models.Model):
    _name = "print.field"
    _description = "Print field mapping"
    _rec_name = "target_field"
    _parent_name = "report_id"

    report_id = fields.Many2one("print.report")

    source_field = fields.Char()
    target_field = fields.Char(required=True)
    target_model_id = fields.Many2one(related="report_id.target_model_id")
    field_type = fields.Char(compute="_compute_field_type", store=True)

    static_value = fields.Char()
    formatting = fields.Char()

    @api.depends("source_field")
    def _compute_field_type(self):
        for rec in self:
            if rec.static_value:
                rec.field_type = "char"

            if not rec.source_field:
                continue

            parts = rec.source_field.split(".")
            model = self.env[rec.target_model_id.model]
            target_field = None

            if len(parts) == 1:
                field = parts[0]
                if field not in model._fields:
                    raise ValidationError(
                        self.env._(
                            "Field %(field)s does not exist on model %(model)s",
                            field=field,
                            model=model,
                        )
                    )
                target_field = model._fields__[field]
            else:
                for i, field in enumerate(parts):
                    if field not in model._fields:
                        raise ValidationError(
                            self.env._(
                                "Field %(field)s does not exist on model %(model)s",
                                field=field,
                                model=model,
                            )
                        )
                    target_field = model._fields[field]
                    if i < len(parts) - 1:
                        if not target_field.comodel_name:
                            raise ValidationError(
                                self.env._(
                                    "Field %(field)s on %(model)s is not relational",
                                    field=target_field,
                                    model=model,
                                )
                            )
                        model = self.env[target_field.comodel_name]
            rec.field_type = target_field.type

    def get_value(self, record=None):
        self.ensure_one()

        if self.static_value:
            return self.static_value

        record.ensure_one()

        if not self.source_field:
            raise ValidationError(
                self.env._("Cannot get value if 'source_field' is missing!")
            )

        if not self.target_model_id:
            raise ValidationError(
                self.env._("Cannot get value if 'model_id is missing!")
            )

        res = record.mapped(self.source_field)

        if len(res) == 0:
            raise ValidationError(
                self.env._(
                    "No value found for mapping %(mapping)s on record %(record)s",
                    mapping=self.source_field,
                    record=self,
                )
            )
        elif len(res) > 1:
            raise ValidationError(
                self.env._(
                    "Multiple values found for mapping %(mapping)s "
                    "on record %(record)s",
                    mapping=self.source_field,
                    record=self,
                )
            )

        return res[0]

    def get_formatted_value(self, record):
        self.ensure_one()
        record.ensure_one()
        value = self.get_value(record)

        match value:
            case models.BaseModel():
                value = value.display_name or value.name
            case _:
                pass

        return value
