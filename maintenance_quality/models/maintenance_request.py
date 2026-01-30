import logging

from odoo import api, fields, models

from odoo.addons.quality.models.quality import QualityCheck

_logger = logging.getLogger(__name__)


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    quality_check_ids = fields.One2many(
        "quality.check", "maintenance_request_id", "Quality Checks"
    )
    quality_check_todo_count = fields.Integer(compute="_compute_check")
    quality_check_todo = fields.Boolean(compute="_compute_check")
    quality_check_pass_count = fields.Integer(compute="_compute_check")
    quality_check_fail_count = fields.Integer(compute="_compute_check")

    quality_alert_ids = fields.One2many(
        "quality.alert", "maintenance_request_id", "Quality Alerts"
    )
    quality_alert_count = fields.Integer(
        "Quality Alerts Count", compute="_compute_alert_count"
    )

    @api.depends("quality_check_ids", "quality_check_ids.quality_state")
    def _compute_check(self):
        for request in self:
            request.quality_check_todo_count = len(
                request.quality_check_ids.filtered(
                    lambda check: check.quality_state == "none"
                )
            )

            request.quality_check_pass_count = len(
                request.quality_check_ids.filtered(
                    lambda check: check.quality_state == "pass"
                )
            )

            request.quality_check_fail_count = len(
                request.quality_check_ids.filtered(
                    lambda check: check.quality_state == "fail"
                )
            )

            request.quality_check_todo = any(
                [
                    state == "none"
                    for state in request.quality_check_ids.mapped("quality_state")
                ]
            )

    @api.depends("quality_alert_ids")
    def _compute_alert_count(self):
        for request in self:
            request.quality_alert_count = len(request.quality_alert_ids)

    def _get_quality_point_domain(self):
        self.ensure_one()
        domain = []
        if self.equipment_id:
            domain.append(("equipment_ids", "in", [self.equipment_id.id]))
        if self.equipment_id.category_id:
            domain.append(
                ("equipment_category_ids", "in", [self.equipment_id.category_id.id])
            )

        if self.workcenter_id:
            domain.append(("workcenter_ids", "in", [self.workcenter_id.id]))

        if self.equipment_id.workcenter_id:
            domain.append(
                ("workcenter_ids", "in", [self.equipment_id.workcenter_id.id])
            )

        for _i in range(len(domain) - 1):
            domain.insert(0, "|")

        match self.maintenance_type:
            case "preventive":
                domain.append(("check_preventive", "=", True))
            case "corrective":
                domain.append(("check_corrective", "=", True))

        domain.append(("control_point_type", "=", "maintenance"))
        domain.insert(0, "&")

        return domain

    def _check_for_quality_checks(self):
        self.ensure_one()

        domain = self._get_quality_point_domain()
        quality_points = self.env["quality.point"].search(domain)

        return quality_points

    def _create_quality_checks(self):
        for request in self:
            qcps = request._check_for_quality_checks()
            checks: QualityCheck = self.env["quality.check"]
            for qcp in qcps:
                checks += self.env["quality.check"].create(
                    {
                        "point_id": qcp.id,
                        "maintenance_request_id": request.id,
                        "quality_state": "none",
                        "team_id": qcp.team_id.id,
                        "company_id": qcp.company_id.id,
                        "workcenter_id": request.workcenter_id.id,
                        "equipment_id": request.equipment_id.id,
                    }
                )

            request.quality_check_ids = checks

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res._create_quality_checks()
        return res

    def action_view_quality_checks(self):
        self.ensure_one()

        tree_view = self.env.ref(
            "maintenance_quality.view_quality_check_tree_maintenance"
        ).id

        if len(self.quality_check_ids) == 1:
            action = {
                "name": self.env._("Quality Checks"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "views": [(False, "form")],
                "res_model": "quality.check",
                "res_id": self.quality_check_ids.ids[0],
            }

        else:
            action = {
                "name": self.env._("Quality Checks"),
                "type": "ir.actions.act_window",
                "view_mode": "list,form",
                "views": [
                    (tree_view, "list"),
                    (False, "form"),
                ],
                "res_model": "quality.check",
                "domain": [("maintenance_request_id", "=", self.id)],
            }
        return action

    def action_view_quality_checks_fail(self):
        self.ensure_one()
        failed_checks = self.quality_check_ids.filtered(
            lambda check: check.quality_state == "fail"
        )

        if len(failed_checks) == 1:
            return {
                "name": self.env._("Quality Checks"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "quality.check",
                "res_id": failed_checks[0].id,
            }
        else:
            return {
                "name": self.env._("Quality Checks"),
                "type": "ir.actions.act_window",
                "view_mode": "list,form",
                "res_model": "quality.check",
                "domain": [
                    ("maintenance_request_id", "=", self.id),
                    ("quality_state", "=", "fail"),
                ],
            }

    def action_view_quality_checks_pass(self):
        self.ensure_one()
        failed_checks = self.quality_check_ids.filtered(
            lambda check: check.quality_state == "pass"
        )

        if len(failed_checks) == 1:
            return {
                "name": self.env._("Quality Checks"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "quality.check",
                "res_id": failed_checks[0].id,
            }
        else:
            return {
                "name": self.env._("Quality Checks"),
                "type": "ir.actions.act_window",
                "view_mode": "list,form",
                "res_model": "quality.check",
                "domain": [
                    ("maintenance_request_id", "=", self.id),
                    ("quality_state", "=", "pass"),
                ],
            }

    def action_view_quality_alerts(self):
        self.ensure_one()

        if len(self.quality_alert_ids) == 1:
            return {
                "name": self.env._("Quality Alerts"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "quality.alert",
                "res_id": self.quality_alert_ids[0].id,
            }
        else:
            return {
                "name": self.env._("Quality Alerts"),
                "type": "ir.actions.act_window",
                "view_mode": "list,form",
                "res_model": "quality.alert",
                "domain": [
                    ("maintenance_request_id", "=", self.id),
                ],
            }
