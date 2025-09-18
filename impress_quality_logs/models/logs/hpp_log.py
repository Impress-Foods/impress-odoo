import logging
from datetime import datetime
from math import floor

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HppLog(models.Model):
    _name = "hpp.log"
    _description = "Hpp_log"
    _inherit = "log.mixin"

    log_line_ids = fields.One2many(
        comodel_name="hpp.log.line", inverse_name="hpp_log_id"
    )

    qty_produced = fields.Integer(
        "Quantity Produced", compute="_compute_qty_produced", store=True
    )
    qty_total = fields.Integer(
        "Total Quantity", compute="_compute_qty_total", store=True
    )
    qty_cases = fields.Integer(
        "Quantity Cases", compute="_compute_qty_cases", store=True
    )
    qty_redone = fields.Integer("Quantity Redone")
    qty_scrapped = fields.Integer("Quantity Scrapped")
    qty_quality = fields.Integer("Quantity Quality")

    hpp_report = fields.Binary("HPP Report")

    monthly_signature = fields.Binary()
    monthly_signature_date = fields.Datetime(
        compute="_compute_monthly_signature_date", store=True
    )

    @api.depends("monthly_signature")
    def _compute_monthly_signature_date(self):
        for rec in self:
            if rec.monthly_signature:
                rec.monthly_signature_date = datetime.now()

    @api.depends("qty_total", "qty_quality", "qty_scrapped", "qty_redone")
    def _compute_qty_produced(self):
        for log in self:
            log.qty_produced = (
                log.qty_total - log.qty_redone - log.qty_scrapped - log.qty_quality
            )

    @api.depends("log_line_ids.total_qty")
    def _compute_qty_total(self):
        for log in self:
            log.qty_total = sum(log.log_line_ids.mapped("total_qty"))

    @api.depends(
        "qty_produced",
        "production_id.product_id",
        "production_id.product_id.qty_multiple",
    )
    def _compute_qty_cases(self):
        for log in self:
            qty_per_case = log.production_id.product_id.qty_multiple
            if qty_per_case > 0:
                log.qty_cases = floor(log.qty_produced / qty_per_case)
            else:
                log.qty_cases = log.qty_produced

    def action_view_hpp_lines(self):
        self.ensure_one()
        action = {
            "res_model": "hpp.log.line",
            "type": "ir.actions.act_window",
            "view_mode": "list,form",
            "domain": [("hpp_log_id", "=", self.id)],
        }
        return action
