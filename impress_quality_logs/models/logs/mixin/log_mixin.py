import logging
from ast import literal_eval
from datetime import datetime

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class LogMixin(models.Model):
    _name = "log.mixin"
    _description = "log.mixin"

    name = fields.Char()
    signature = fields.Binary()

    quality_check_id = fields.Many2one("quality.check")
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

    lot_id = fields.Many2one(
        "stock.lot",
        "Lot",
        related="production_id.lot_producing_id",
        store=True,
        depends=["production_id", "production_id.lot_producing_id"],
    )

    date = fields.Datetime(
        "Date",
        related="quality_check_id.control_date",
        store=True,
        depends=["quality_check_id", "quality_check_id.control_date"],
    )
    weekly_signature_date = fields.Datetime(
        compute="_compute_weekly_signature_date", store=True
    )

    quality_notes = fields.Text()

    @api.depends("signature")
    def _compute_weekly_signature_date(self):
        for rec in self:
            if rec.signature:
                rec.weekly_signature_date = datetime.now()

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
