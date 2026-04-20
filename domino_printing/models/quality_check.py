import logging

from odoo import models

from .domino import DominoAPI

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
        case_template = None
        code_template = None

        if self.point_id.print_case:
            case_template = self.point_id.case_domino_template

        if self.point_id.print_code:
            code_template = self.point_id.coding_domino_template

        if case_template or code_template:
            dom = DominoAPI(
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("domino_printing.api_endpoint"),
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("domino_printing.api_key"),
            )
            if code_template:
                dom.send_print_job(
                    self.operation_id.workcenter_id.domino_code_printer_id.printer_id,
                    code_template.domino_label_id.name,
                    code_template._make_json_payload(self),
                )
            if case_template:
                dom.send_print_job(
                    self.operation_id.workcenter_id.domino_case_printer_id.printer_id,
                    case_template.domino_label_id.name,
                    case_template._make_json_payload(self),
                )

        return {}
