import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class LogLineMixin(models.AbstractModel):
    _name = "log_line.mixin"
    _description = "Log Line mixin"

    start_date = fields.Datetime()
    notes = fields.Text()
    signature = fields.Binary()

    production_id = fields.Many2one(
        "mrp.production",
        "Production Order",
        related="quality_check_id.production_id",
        store=True,
        depends=["quality_check_id", "quality_check_id.production_id"],
    )
    product_id = fields.Many2one(
        "product.product",
        "Product",
        related="production_id.product_id",
        store=True,
        depends=["production_id", "production_id.product_id"],
    )
    product_lot_id = fields.Many2one(
        "stock.lot", "Lot", store=True, compute="_compute_product_lot_id"
    )

    quality_check_id = fields.Many2one("quality.check", "Quality Check")
    active_worksheet_field = fields.Char(
        compute="_compute_active_worksheet_field", store=True
    )
    is_locked = fields.Boolean("Locked")

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

    @api.depends(lambda self: ["quality_check_id"] + self._get_worksheet_fields())
    def _compute_active_worksheet_field(self):
        for record in self:
            if not record.active_worksheet_field:
                # The worksheet relational field(s) are not known
                # to the model when it's created in the DB.
                # We expect those relational field(s) to
                # contain 'x_worksheet' in their name
                # since they are:
                #   A) Custom fields (and need to start with 'x_')
                #   B) follow the 'x_' with 'worksheet' by convention

                worksheet_fields = record._get_worksheet_fields()
                worksheet_field = [f for f in worksheet_fields if record[f]]

                if worksheet_field:
                    # Since the worksheet fields are set from the worksheet
                    # containing the new record at creation, we can assume
                    # that only one worksheet field is set. We can when take
                    # the first (and only) one in the list
                    record.active_worksheet_field = worksheet_field[0]

    # Hooking into the quality_wizard_id context to be able to set
    # the current quality.check id when creating a new log line.
    # This is used as a work around to the fact that the first log line is
    # created before the worksheet is linked to the quality check.
    # We then always get the quality check id from the wizard
    # context when creating a new log line.
    @api.model_create_multi
    def create(self, vals_list):
        if "quality_wizard_id" in self.env.context:
            wizard = self.env["quality.check.wizard"].browse(
                [self.env.context["quality_wizard_id"]]
            )
            vals_list[0]["quality_check_id"] = wizard.current_check_id.id
        record = super().create(vals_list)
        return record

    def _check_lock(self, vals):
        if "is_locked" in vals and not vals["is_locked"]:
            return True
        if self.is_locked:
            raise ValidationError(_("This record is locked and cannot be modified."))

    def write(self, vals):
        return super().write(vals)

    def action_lock(self):
        if self.is_locked:
            raise UserError(_("This record is already locked."))
        else:
            self.is_locked = True

    def action_unlock(self):
        if self.is_locked:
            self.is_locked = False
        else:
            raise UserError(_("This record is not locked."))

    def sign_log_line(self):
        for rec in self:
            rec.write({"signature": rec.env.user.sign_initials})

    # TODO: Refactor action_view_log into log.line.mixin to reduce maintenance
