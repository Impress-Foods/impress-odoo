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

    def _get_print_qty(self):
        if self.env.context.get("printing_printing_quantity", False):
            return self.env.context.get("printing_printing_quantity")
        return super()._get_print_qty()

    def _get_printer(self):
        """Resolves printers by priority"""
        self.ensure_one()

        if self.env.context.get("printing_printer_override", False):
            printer = self.env["print.printer"].browse(
                self.env.context.get("printing_printer_override")
            )
            if printer:
                return printer.technical_name

        if self.point_id.printer_id:
            return self.point_id.printer_id.technical_name

        if self.workcenter_id.default_printer_id:
            return self.workcenter_id.default_printer_id.technical_name

        raise ValidationError(
            self.env._("No printer could be found for this print job!")
        )
