import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class QualityCheck(models.Model):
    _inherit = "quality.check"

    @api.depends("point_id")
    def _compute_worksheet_template_id(self):
        for check in self:
            if check.point_id and check.point_id.test_type == "worksheet":
                point = check.point_id
                if point.log_type_id:
                    check.worksheet_template_id = (
                        point.log_type_id.active_template_id or False
                    )
                else:
                    check.worksheet_template_id = point.worksheet_template_id
            else:
                check.worksheet_template_id = False
