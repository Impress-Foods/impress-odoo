import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    hpp_log_ids = fields.One2many("hpp.log", "production_id", string="HPP Logs")
    loma_log_ids = fields.One2many("loma.log", "production_id", string="LOMA Logs")
    metal_log_ids = fields.One2many("metal.log", "production_id")
    coding_log_ids = fields.One2many(
        "coding.log",
        "production_id",
    )
    x_ray_log_ids = fields.One2many("x_ray.log", "production_id", string="X-Ray Logs")

    hpp_qty_cases = fields.Float(
        "HPP Quantity", compute="_compute_hpp_qty_cases", store=True
    )

    @api.depends("hpp_log_ids", "hpp_log_ids.qty_cases")
    def _compute_hpp_qty_cases(self):
        for record in self:
            if len(record.hpp_log_ids) != 0:
                record.hpp_qty_cases = record.hpp_log_ids[0].qty_cases
            else:
                record.hpp_qty_cases = 0

    def action_view_hpp_log(self):
        self.ensure_one()
        action = {
            "res_model": "hpp.log",
            "type": "ir.actions.act_window",
        }

        if len(self.hpp_log_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.hpp_log_ids.id})

        else:
            action.update(
                {
                    "name": self.env._(f"HPP Logs for {self.name}"),
                    "domain": [("id", "in", self.hpp_log_ids.ids)],
                    "view_mode": "list,form",
                }
            )

        return action

    def action_view_metal_log(self):
        self.ensure_one()
        action = {
            "res_model": "metal.log",
            "type": "ir.actions.act_window",
        }

        if len(self.metal_log_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.metal_log_ids.id})

        else:
            action.update(
                {
                    "name": self.env._(f"Metal Logs for {self.name}"),
                    "domain": [("id", "in", self.metal_log_ids.ids)],
                    "view_mode": "list,form",
                }
            )

        return action

    def action_view_loma_log(self):
        self.ensure_one()
        action = {
            "res_model": "loma.log",
            "type": "ir.actions.act_window",
        }

        if len(self.loma_log_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.loma_log_ids.id})

        else:
            action.update(
                {
                    "name": self.env._(f"LOMA Logs for {self.name}"),
                    "domain": [("id", "in", self.loma_log_ids.ids)],
                    "view_mode": "list,form",
                }
            )

        return action

    def action_view_coding_log(self):
        self.ensure_one()
        action = {
            "res_model": "coding.log",
            "type": "ir.actions.act_window",
        }

        if len(self.coding_log_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.coding_log_ids.id})

        else:
            action.update(
                {
                    "name": self.env._(f"Coding Logs for {self.name}"),
                    "domain": [("id", "in", self.coding_log_ids.ids)],
                    "view_mode": "list,form",
                }
            )

        return action

    def action_view_x_ray_log(self):
        self.ensure_one()
        action = {
            "res_model": "x_ray.log",
            "type": "ir.actions.act_window",
        }

        if len(self.x_ray_log_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.x_ray_log_ids.id})

        else:
            action.update(
                {
                    "name": self.env._(f"X-Ray Logs for {self.name}"),
                    "domain": [("id", "in", self.x_ray_log_ids.ids)],
                    "view_mode": "list,form",
                }
            )

        return action
