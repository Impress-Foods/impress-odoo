import datetime
from typing import Any

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..tools import date_formatter, string_formatter


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

    translate = fields.Boolean()

    languages = fields.Many2many(comodel_name="res.lang")

    @api.constrains("target_field")
    def _check_target_field(self):
        for record in self:
            if record.target_field[0] == "_":
                raise ValidationError(
                    self.env._("Target field cannot be start with '_'!")
                )

    @api.depends("source_field")
    def _compute_field_type(self):
        for rec in self:
            if rec.static_value:
                rec.field_type = "char"
                continue

            if not rec.source_field:
                continue

            parts = rec.source_field.split(".")
            model: models.Model = self.env[rec.target_model_id.model]
            target_field = None

            if len(parts) == 1:
                field = parts[0]
                target_field = self._get_field(model, field)

            else:
                for i, field in enumerate(parts):
                    target_field = self._get_field(model, field)
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

    def get_value(self, record=None) -> Any:
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
            case datetime.datetime():
                assert isinstance(value, datetime.datetime)
                value = date_formatter.format_date(value, self.formatting)
            case str():
                assert isinstance(value, str)
                value = string_formatter.format_string(value, self.formatting)
            case _:
                pass

        return value

    @api.model
    def _get_field(self, model: models.Model, field: str):
        if field not in model._fields:
            raise ValidationError(
                self.env._(
                    "Field %(field)s does not exist on model %(model)s",
                    field=field,
                    model=model,
                )
            )
        return model._fields[field]
