import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class LogLineMixin(models.AbstractModel):
    _name = "log_line.mixin"
    _description = "Log Line mixin"

    start_date = fields.Datetime()
    notes = fields.Text()
    signature = fields.Binary()

    # Name of the Many2one to the log on the concrete line model
    # (e.g. "hpp_log_id"). The worksheet field pointing to that log is
    # expected to be named "x_" + _log_field (e.g. "x_hpp_log_id").
    _log_field: str = ""

    quality_check_id = fields.Many2one("quality.check", "Quality Check")
    # The log is the source of truth for the production. Lines without a log
    # fall back to their check, which was the only source before 19.0.1.1.0.
    production_id = fields.Many2one(
        "mrp.production",
        "Production Order",
        compute="_compute_production_id",
        store=True,
    )
    product_id = fields.Many2one(
        "product.product",
        "Product",
        related="production_id.product_id",
        store=True,
    )
    product_lot_id = fields.Many2one(
        "stock.lot", "Lot", store=True, compute="_compute_product_lot_id"
    )

    # Deprecated since 19.0.1.1.0: no longer used for linking. Kept so the
    # stored column stays readable by any filter or report relying on it.
    active_worksheet_field = fields.Char(
        compute="_compute_active_worksheet_field", store=True
    )
    is_locked = fields.Boolean("Locked")

    @api.depends(
        lambda self: ([f"{self._log_field}.production_id"] if self._log_field else [])
        + ["quality_check_id.production_id"]
    )
    def _compute_production_id(self):
        for record in self:
            log = record[record._log_field] if record._log_field else None
            record.production_id = (
                log and log.production_id
            ) or record.quality_check_id.production_id

    @api.depends("production_id", "production_id.lot_producing_ids")
    def _compute_product_lot_id(self):
        for record in self:
            if len(record.production_id.lot_producing_ids) != 0:
                record.product_lot_id = record.production_id.lot_producing_ids[0]
            else:
                record.product_lot_id = False

    def _get_worksheet_fields(self):
        # The current model name needs to be fetched dynamically,
        # since it could be any model inheriting this mixin
        current_model = self.env[self._name]
        # Get all fields matching our criteria and then get the fields which are set
        worksheet_fields = [
            k for k in current_model.fields_get().keys() if "x_worksheet" in k
        ]
        return worksheet_fields

    @api.depends("quality_check_id")
    def _compute_active_worksheet_field(self):
        for record in self:
            if record.active_worksheet_field:
                continue
            if not record.active_worksheet_field:
                # The worksheet relational field(s) are not known
                # to the model when it's created in the DB.
                # We expect those relational field(s) to
                # contain 'x_worksheet' in their name
                # since they are:
                #   A) Custom fields (and need to start with 'x_')
                #   B) follow the 'x_' with 'worksheet' by convention

                worksheet_fields = [
                    name
                    for name, field in self._fields.items()
                    if name.startswith("x_worksheet") or "x_worksheet" in name
                ]
                found_field = next((f for f in worksheet_fields if record[f]), False)

                if found_field:
                    # Since the worksheet fields are set from the worksheet
                    # containing the new record at creation, we can assume
                    # that only one worksheet field is set. We can when take
                    # the first (and only) one in the list
                    record.active_worksheet_field = found_field

    @api.model_create_multi
    def create(self, vals_list):
        """Link new lines to their check and log (extends BaseModel.create).

        Check: from the quality check wizard context (the worksheet form is
        opened from it), otherwise from the worksheet the line is created in.

        Log: an explicit value or a default_<log field> context wins (e.g. the
        log's "view lines" list); otherwise the log of the worksheet.
        """
        wizard_check = self._get_wizard_check()
        default_log_key = f"default_{self._log_field}"
        for vals in vals_list:
            worksheet = self._get_worksheet_from_vals(vals)
            if "quality_check_id" not in vals and wizard_check:
                vals["quality_check_id"] = wizard_check.id
            if not vals.get("quality_check_id") and worksheet:
                vals["quality_check_id"] = worksheet.x_quality_check_id.id
            if (
                self._log_field
                and not vals.get(self._log_field)
                and default_log_key not in self.env.context
                and worksheet
            ):
                log = self._get_worksheet_log(worksheet)
                if log:
                    vals[self._log_field] = log.id
        return super().create(vals_list)

    def _get_wizard_check(self):
        wizard_id = self.env.context.get("quality_wizard_id")
        if not wizard_id:
            return self.env["quality.check"]
        return self.env["quality.check.wizard"].browse(wizard_id).current_check_id

    @api.model
    def _get_worksheet_from_vals(self, vals: dict) -> models.BaseModel | None:
        """Return the worksheet set in ``vals`` through an x_worksheet_* field."""
        for name, value in vals.items():
            field = self._fields.get(name)
            if (
                value
                and name.startswith("x_worksheet")
                and field is not None
                and field.type == "many2one"
            ):
                return self.env[field.comodel_name].browse(value)
        return None

    @api.model
    def _get_worksheet_log(self, worksheet: models.BaseModel) -> models.BaseModel:
        worksheet_log_field = f"x_{self._log_field}"
        if worksheet_log_field not in worksheet._fields:
            return self.env[self._fields[self._log_field].comodel_name]
        return worksheet[worksheet_log_field]

    def _check_lock(self, vals):
        if "is_locked" in vals and not vals["is_locked"]:
            return True
        if self.is_locked:
            raise ValidationError(
                self.env._("This record is locked and cannot be modified.")
            )

    def write(self, vals):
        return super().write(vals)

    def action_lock(self):
        if self.is_locked:
            raise UserError(self.env._("This record is already locked."))
        else:
            self.is_locked = True

    def action_unlock(self):
        if self.is_locked:
            self.is_locked = False
        else:
            raise UserError(self.env._("This record is not locked."))

    def sign_log_line(self):
        for rec in self:
            rec.write({"signature": rec.env.user.sign_initials})

    # TODO: Refactor action_view_log into log.line.mixin to reduce maintenance
