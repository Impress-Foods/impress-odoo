from odoo import api, fields, models


class WorkCenter(models.Model):
    _inherit = "mrp.workcenter"

    domino_case_printer_id = fields.Many2one("domino.work.center")
    domino_code_printer_id = fields.Many2one("domino.work.center")
    domino_valid_work_center_ids = fields.Many2many(
        "domino.work.center",
        store=True,
        compute="_compute_domino_valid_work_center_ids",
    )
    domino_available_label_ids = fields.Many2many(
        "domino.label", compute="_compute_domino_available_label_ids", store=True
    )

    @api.depends(
        "domino_case_printer_id",
        "domino_code_printer_id",
        "domino_case_printer_id.label_ids",
        "domino_code_printer_id.label_ids",
    )
    def _compute_domino_available_label_ids(self):
        for record in self:
            record.domino_available_label_ids = record.domino_case_printer_id.mapped(
                "label_ids"
            ) + record.domino_code_printer_id.mapped("label_ids")

    @api.depends("domino_case_printer_id", "domino_code_printer_id")
    def _compute_domino_valid_work_center_ids(self):
        for record in self:
            record.domino_valid_work_center_ids = (
                record.domino_case_printer_id + record.domino_code_printer_id
            )
