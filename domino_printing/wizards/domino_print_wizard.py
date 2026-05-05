import logging

from odoo import fields, models

from ..models.domino import DominoAPI

_logger = logging.getLogger(__name__)


class DominoPrintWizard(models.TransientModel):
    _name = "domino.wizard.print"
    _description = "Domino Print Wizard"

    qcc_id = fields.Many2one("quality.check")
    code_template = fields.Many2one(related="qcc_id.point_id.coding_domino_template")
    case_template = fields.Many2one(related="qcc_id.point_id.case_domino_template")

    code_printer_ids = fields.Many2many("domino.printer", "domino_wizard_code_printers")
    case_printer_ids = fields.Many2many("domino.printer", "domino_wizard_case_printers")

    print_case = fields.Boolean()
    print_code = fields.Boolean()

    code_printer_id = fields.Many2one("domino.printer")
    case_printer_id = fields.Many2one("domino.printer")

    def action_print(self):
        self.ensure_one()
        if self.case_template or self.code_template:
            dom = DominoAPI(self.env)
            if self.code_template:
                dom.send_print_job(
                    self.code_printer_id.printer_id,
                    self.code_template.domino_label_id.name,
                    self.code_template._make_json_payload(self.qcc_id),
                )
            if self.case_template:
                dom.send_print_job(
                    self.case_printer_id.printer_id,
                    self.case_template.domino_label_id.name,
                    self.case_template._make_json_payload(self.qcc_id),
                )
        return {"type": "ir.actions.act_window_close"}
