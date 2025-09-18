import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CodingLogLine(models.Model):
    _name = "coding.log.line"
    _description = "Coding_log_line"
    _inherit = "log_line.mixin"
    _rec_name = "sequence"

    coding_log_id = fields.Many2one(
        comodel_name="coding.log", compute="_compute_coding_log_id", store=True
    )

    sequence = fields.Char(default=lambda self: self.env._("New"), copy=False)

    case_code = fields.Char()
    unit_code = fields.Char()

    unit_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])
    sleeve_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])
    case_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])
    subunit_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])
    shelf_life_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])
    keep_cold_check = fields.Selection([("ok", "Ok"), ("not_ok", "Not Ok")])

    global_success_check = fields.Selection(
        [("ok", "Ok"), ("not_ok", "Not Ok")],
        store=True,
        compute="_compute_global_success_check",
    )

    @api.depends("quality_check_id")
    def _compute_coding_log_id(self):
        for record in self:
            # Get the current worksheet field
            ws = record.active_worksheet_field
            if ws:
                record.coding_log_id = record[ws].x_coding_log_id
            else:
                record.coding_log_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "sequence" not in vals or vals["sequence"] == self.env._("New"):
                vals["sequence"] = self.env["ir.sequence"].next_by_code(
                    "coding_log_line"
                ) or self.env._("New")
        return super().create(vals_list)

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
            if (
                rec.unit_check == "ok"
                and rec.sleeve_check == "ok"
                and rec.case_check == "ok"
                and rec.subunit_check == "ok"
                and rec.shelf_life_check == "ok"
                and rec.keep_cold_check == "ok"
            ):
                rec.global_success_check = "ok"
            else:
                rec.global_success_check = "not_ok"

    def action_view_log(self):
        self.ensure_one()
        action = {
            "res_model": "coding.log",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_id": self.coding_log_id.id,
        }
        return action
