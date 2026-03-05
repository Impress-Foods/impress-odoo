import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HPPLogLine(models.Model):
    _name = "hpp.log.line"
    _inherit = "log_line.mixin"
    _description = "HPP_log_line"

    _rec_name = "cycle_number"

    hpp_log_id = fields.Many2one(
        comodel_name="hpp.log", compute="_compute_hpp_log_id", store=True
    )

    _check_cycle_number = models.Constraint(
        "UNIQUE(cycle_number, production_id)",
        "Cycle Number must be unique for a production!",
    )

    cycle_number = fields.Integer()
    cycle_time = fields.Selection(
        [("120sec", "120 seconds"), ("300sec", "300 seconds")],
    )
    pressure_reached = fields.Integer()
    is_cleaning_cycle = fields.Boolean("Is cleaning cycle?")

    barrel_1_qty = fields.Integer("Barrel 1 Quantity")
    barrel_2_qty = fields.Integer("Barrel 2 Quantity")
    barrel_3_qty = fields.Integer("Barrel 3 Quantity")
    barrel_4_qty = fields.Integer("Barrel 4 Quantity")

    total_qty = fields.Integer(
        "Total Quantity", compute="_compute_total_qty", store=True
    )

    @api.depends(
        "barrel_1_qty",
        "barrel_2_qty",
        "barrel_3_qty",
        "barrel_4_qty",
        "is_cleaning_cycle",
    )
    def _compute_total_qty(self):
        for record in self:
            record._cleaning_cycle_check()
            record.total_qty = (
                record.barrel_1_qty
                + record.barrel_2_qty
                + record.barrel_3_qty
                + record.barrel_4_qty
            )

    @api.depends("quality_check_id")
    def _compute_hpp_log_id(self):
        for record in self:
            # Get the current worksheet field
            ws = record.active_worksheet_field
            if ws:
                record.hpp_log_id = record[ws].x_hpp_log_id
            else:
                record.hpp_log_id = False

    def _cleaning_cycle_check(self):
        for record in self:
            if record.is_cleaning_cycle:
                if (
                    record.barrel_1_qty != 0
                    or record.barrel_2_qty != 0
                    or record.barrel_3_qty != 0
                    or record.barrel_4_qty != 0
                ):
                    raise ValidationError(
                        self.env._("Barrels must be empty during cleaning cycle")
                    )

    def action_view_log(self):
        self.ensure_one()
        action = {
            "res_model": "hpp.log",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_id": self.hpp_log_id.id,
        }
        return action
