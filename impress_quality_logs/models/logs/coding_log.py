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

    # == Deprecated (08-2026) fields, kept for backward compatibility ==
    unit_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])
    case_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok"), ("na", "N/A")])
    sleeve_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])
    subunit_check = fields.Selection(
        [("ok", "Ok"), ("not_ok", "Not Ok"), ("na", "N/A")]
    )
    shelf_life_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])
    keep_cold_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])

    # == New fields (08-2026) ==
    date_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])
    barcode_check = fields.Selection(
        [("ok", "Ok"), ("not_ok", "Not Ok"), ("na", "N/A")]
    )
    packaging_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])
    picture = fields.Binary()

    global_success_check = fields.Selection(
        [("ok", "Ok"), ("not_ok", "Not Ok")],
        store=True,
        compute="_compute_global_success_check",
    )

    operator_signature = fields.Binary()

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

        return (
            self.unit_check == "ok"
            and self.sleeve_check == "ok"
            and self.case_check == "ok"
            and self.subunit_check == "ok"
            and self.shelf_life_check == "ok"
            and self.keep_cold_check == "ok"
        )

    @api.depends("signature")
    def _compute_weekly_signature_date(self):
        for rec in self:
            if rec.signature:
                rec.weekly_signature_date = datetime.now(tz=datetime.timezone.utc)

    def action_sign_log(self):
        for rec in self:
            if not rec.signature:
                rec.signature = rec.env.user.sign_initials
