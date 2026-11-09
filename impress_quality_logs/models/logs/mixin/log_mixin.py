import logging
from ast import literal_eval
from datetime import datetime

from odoo import api, fields, models

from odoo.addons.mrp.models.mrp_production import MrpProduction
from odoo.addons.quality.models.quality import QualityCheck

_logger = logging.getLogger(__name__)


class LogMixin(models.AbstractModel):
    _name = "log.mixin"
    _description = "log.mixin"

    name = fields.Char()
    signature = fields.Binary()

    quality_check_id = fields.Many2one("quality.check")
    # The log is the anchor between a production and everything recorded for
    # it (worksheets, lines). The production is set explicitly when the log is
    # created; the compute only fills it from the check for code paths that
    # create a log with a check alone (kept for backwards compatibility).
    production_id = fields.Many2one(
        "mrp.production",
        "Production Order",
        compute="_compute_production_id",
        store=True,
        readonly=False,
    )
    product_id = fields.Many2one(
        "product.product",
        "Product",
        related="production_id.product_id",
        store=True,
        depends=["production_id", "production_id.product_id"],
    )

    lot_id = fields.Many2one(
        "stock.lot",
        "Lot",
        compute="_compute_lot_id",
        store=True,
    )

    date = fields.Datetime(
        "Date",
        related="quality_check_id.control_date",
        store=True,
        depends=["quality_check_id", "quality_check_id.control_date"],
    )
    weekly_signature_date = fields.Datetime(
        compute="_compute_weekly_signature_date",
        inverse="_inverse_weekly_signature_date",
        store=True,
        string="Daily Signature Date",
    )

    quality_notes = fields.Text()

    _production_uniq = models.Constraint(
        "UNIQUE(production_id)",
        "A production can only have one log of each type.",
    )

    @api.depends("quality_check_id.production_id")
    def _compute_production_id(self):
        for rec in self:
            rec.production_id = rec.quality_check_id.production_id or rec.production_id

    @api.model
    def _get_or_create_for_production(
        self, production: MrpProduction, check: QualityCheck
    ) -> "LogMixin":
        """Return the log of ``production``, creating it from ``check`` if needed.

        Lookup order:
        1. by production: the reference link, which survives MO renames
           (splitting an MO renames it to <name>-001);
        2. by name, for logs whose production is not set (legacy behaviour of
           the worksheet computes, which matched on the production name).

        A check without production keeps the legacy behaviour: all such
        worksheets share the log whose name is empty.
        """
        log = self.browse()
        if production:
            log = self.search([("production_id", "=", production.id)], limit=1)
        if not log:
            log = self.search(
                [("production_id", "=", False), ("name", "=", production.name)],
                limit=1,
            )
        if not log:
            log = self.create(
                {
                    "name": production.name,
                    "quality_check_id": check.id,
                    "production_id": production.id,
                }
            )
        return log

    @api.depends("signature")
    def _compute_weekly_signature_date(self):
        for rec in self:
            if rec.signature:
                rec.weekly_signature_date = datetime.now()

    def _inverse_weekly_signature_date(self):
        return

    @api.depends("production_id", "production_id.lot_producing_ids")
    def _compute_lot_id(self):
        for rec in self:
            rec.lot_id = (
                rec.production_id.lot_producing_ids[0]
                if rec.production_id.lot_producing_ids
                else False
            )

    def action_sign_log(self):
        for rec in self:
            if not rec.signature:
                rec.signature = rec.env.user.sign_initials

    # TODO: Refactor action_view_log_lines into mixin to reduce maintenance

    def action_view_linked_production(self):
        self.ensure_one()
        action = {
            "res_model": "mrp.production",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_id": self.production_id.id,
        }
        return action

    def action_quality_worksheet(self):
        check = self.quality_check_id
        action = check.worksheet_template_id.action_id.sudo().read()[0]
        worksheet = self.env[check.worksheet_template_id.model_id.sudo().model].search(  # type: ignore
            [("x_quality_check_id", "=", check.id)]
        )
        context = literal_eval(action.get("context", "{}"))
        action_name = check._get_check_action_name()
        action.update(
            {
                "name": action_name,
                "res_id": worksheet.id if worksheet else False,
                "views": [(False, "form")],
                "target": "new",
                "context": {
                    **context,
                    "edit": False,
                    "default_x_quality_check_id": check.id,
                },
            }
        )
        return action
