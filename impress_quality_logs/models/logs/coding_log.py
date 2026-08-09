import logging
from datetime import datetime

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CodingLog(models.Model):
    _inherit = "log.mixin"
    _name = "coding.log"
    _description = "Coding Log"

    shelf_life = fields.Integer(related="product_id.expiration_time")
    case_code = fields.Char()
    unit_code = fields.Char()

    notes = fields.Char()
    start_date = fields.Datetime()

    unit_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok"), ("na", "N/A")])
    sleeve_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok"), ("na", "N/A")])
    case_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok"), ("na", "N/A")])
    subunit_check = fields.Selection(
        [("ok", "Ok"), ("not_ok", "Not Ok"), ("na", "N/A")]
    )
    shelf_life_check = fields.Selection(
        [("ok", "Ok"), ("not_ok", "Not Ok"), ("na", "N/A")]
    )
    keep_cold_check = fields.Selection(
        [("ok", "Ok"), ("not_ok", "Not Ok"), ("na", "N/A")]
    )

    global_success_check = fields.Selection(
        [("ok", "Ok"), ("not_ok", "Not Ok")],
        store=True,
        compute="_compute_global_success_check",
    )

    operator_signature = fields.Binary()

    log_type = fields.Selection(
        [
            ("bottles", "Bottles"),
            ("cases", "Cases"),
        ]
    )

    @api.depends(
        "unit_check",
        "sleeve_check",
        "case_check",
        "subunit_check",
        "shelf_life_check",
        "keep_cold_check",
    )
    def _compute_global_success_check(self):
        for rec in self:
            if rec._check_global_success():
                rec.global_success_check = "ok"
            else:
                rec.global_success_check = "not_ok"

    def _check_global_success(self):
        self.ensure_one()
        return all(
            v in ("ok", "na")
            for v in (
                self.unit_check,
                self.sleeve_check,
                self.case_check,
                self.subunit_check,
                self.shelf_life_check,
                self.keep_cold_check,
            )
        )

    @api.depends("signature")
    def _compute_weekly_signature_date(self):
        for rec in self:
            if rec.signature:
                rec.weekly_signature_date = datetime.now()

    def action_sign_log(self):
        for rec in self:
            if not rec.signature:
                rec.signature = rec.env.user.sign_initials
