import logging

from odoo import models

_logger = logging.getLogger(__name__)


class QualityCheck(models.Model):
    _inherit = "quality.check"

    def _get_product_label_action(self, report_type):
        self.ensure_one()
        if report_type != "domino":
            return super()._get_product_label_action(report_type)

        return self._send_domino_labels()

    def _get_lot_label_action(self, report_type):
        self.ensure_one()

        if report_type != "domino":
            return super()._get_lot_label_action(report_type)

        return self._send_domino_labels()

    def _send_domino_labels(self):
        code_printers = self.mapped(
            "point_id.coding_domino_template.domino_label_id.printer_ids.id"
        )
        case_printers = self.mapped(
            "point_id.case_domino_template.domino_label_id.printer_ids.id"
        )

        action = {
            "name": self.env._("Domino Printing"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "domino.wizard.print",
            "views": [[False, "form"]],
            "target": "new",
            "context": {
                "default_qcc_id": self.id,
                "default_case_printer_ids": case_printers,
                "default_code_printer_ids": code_printers,
                "default_print_code": self.point_id.print_code,
                "default_print_case": self.point_id.print_case,
            },
        }
        return action
