from odoo import models
from odoo.exceptions import ValidationError


class QualityCheck(models.Model):
    _inherit = "quality.check"

    def _get_product_label_action(self, report_type):
        if report_type == "api":
            return self._send_api_label()
        else:
            return super()._get_product_label_action(report_type)

    def _get_lot_label_action(self, report_type):
        if report_type == "api":
            return self._send_api_label()
        else:
            return super()._get_lot_label_action(report_type)

    def _send_api_label(self):
        self.ensure_one()

        report = self.point_id.report_id

        if report.report_type != "api":
            raise ValidationError(
                self.env._(
                    "Trying to print report of type %(type)s via API",
                    type=report.report_type,
                )
            )

        qty = self._get_print_qty()

        lot_id = self.workorder_id.finished_lot_ids.ids
        if len(lot_id) > 1:
            raise ValidationError(
                self.env._("Cannot send label for multiple lots via API")
            )

        if not lot_id:
            raise ValidationError(self.env._("Must specify lot for label printing"))

        res = report.report_action(
            lot_id, data={"qty": qty, "printer": self._get_printer()}
        )
        res["id"] = report.id
        return res

    def _get_printer(self):
        return False
