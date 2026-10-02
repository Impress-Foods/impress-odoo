import datetime
from typing import Any

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..tools import date_formatter, string_formatter


class PrintField(models.Model):
    _name = "print.field"
    _description = "API payload field mapping"
    _rec_name = "target_field"
    _parent_name = "report_id"

    report_id = fields.Many2one(
        comodel_name="print.report",
        required=True,
        ondelete="cascade",
    )
    source_field = fields.Char()
    target_field = fields.Char(required=True)
    target_model_id = fields.Many2one(related="report_id.target_model_id")
    field_type = fields.Char(compute="_compute_field_type")
    static_value = fields.Char()
    formatting = fields.Char()
    translate = fields.Boolean()
    languages = fields.Many2many(comodel_name="res.lang")

    @api.constrains("target_field")
    def _check_target_field(self):
        for record in self:
            if record.target_field.startswith("_"):
                raise ValidationError(
                    self.env._("Target fields cannot start with '_'.")
                )

    @api.constrains("source_field", "static_value", "report_id")
    def _check_source_field(self):
        """Refuse to save a mapping that cannot be resolved.

        Resolution is a compute, and a compute that raises takes the whole
        record down with it.  ``field_type`` is read by the profile form, so a
        mapping left pointing at a field that a dependency removed makes the
        one screen needed to repair it fail to open, and the profile is only
        recoverable through the database.  Validating here puts the error where
        the mistake was made instead.

        A change to the model the profile targets does not write this record,
        so it is covered by ``print.report._check_mapping_fields`` instead.
        """
        for mapping in self:
            mapping._resolve_source_field()

    @api.depends("source_field", "static_value", "report_id.target_model_id")
    def _compute_field_type(self):
        for mapping in self:
            if mapping.static_value:
                mapping.field_type = "char"
                continue
            try:
                field = mapping._resolve_source_field()
            except ValidationError:
                # ``_check_source_field`` reports this when the mapping is
                # written.  A mapping can still reach here broken, from a
                # profile repointed at another model, so the compute degrades
                # to an empty type rather than taking the form down with it.
                mapping.field_type = False
                continue
            mapping.field_type = field.type if field else False

    def _resolve_source_field(self):
        """Return the field ``source_field`` names, walking a dotted path.

        ``None`` means there is nothing to resolve: a static value, no source,
        or a profile without a model.  That is the same state ``field_type``
        reports as empty.  Raises ``ValidationError`` when the path names a
        field that does not exist, or crosses a field that cannot be walked.
        """
        self.ensure_one()
        if self.static_value or not self.source_field or not self.target_model_id:
            return None

        parts = self.source_field.split(".")
        model = self.env[self.target_model_id.model]
        target_field = None
        for index, part in enumerate(parts):
            target_field = self._get_field(model, part)
            if index < len(parts) - 1:
                if not target_field.relational:
                    raise ValidationError(
                        self.env._(
                            "Field %(field)s on %(model)s is not relational.",
                            field=target_field.string or part,
                            model=model._name,
                        )
                    )
                model = self.env[target_field.comodel_name]
        return target_field

    @api.model
    def _get_field(self, model: models.Model, field_name: str):
        if field_name not in model._fields:
            raise ValidationError(
                self.env._(
                    "Field %(field)s does not exist on model %(model)s.",
                    field=field_name,
                    model=model._name,
                )
            )
        return model._fields[field_name]

    def get_value(self, record: models.Model | None = None) -> Any:
        self.ensure_one()
        if self.static_value:
            return self.static_value

        if record is None:
            raise ValidationError(
                self.env._("A record is required to read a mapped field.")
            )
        record.ensure_one()
        if not self.source_field:
            raise ValidationError(
                self.env._("The source field is required for this mapping.")
            )
        if not self.target_model_id:
            raise ValidationError(
                self.env._("The target model is required for this mapping.")
            )

        values = record.mapped(self.source_field)
        if len(values) == 0:
            raise ValidationError(
                self.env._(
                    "No value found for mapping %(mapping)s on record %(record)s.",
                    mapping=self.source_field,
                    record=record.display_name,
                )
            )
        if len(values) > 1:
            raise ValidationError(
                self.env._(
                    "Multiple values found for mapping %(mapping)s "
                    "on record %(record)s.",
                    mapping=self.source_field,
                    record=record.display_name,
                )
            )
        return values[0]

    def get_formatted_value(self, record: models.Model) -> Any:
        self.ensure_one()
        record.ensure_one()
        value = self.get_value(record)

        if isinstance(value, models.BaseModel):
            value = value.display_name or value.name
        elif isinstance(value, (datetime.date, datetime.datetime)):
            value = date_formatter.format_date(value, self.formatting)
        elif isinstance(value, str):
            value = string_formatter.format_string(value, self.formatting)
        return value
