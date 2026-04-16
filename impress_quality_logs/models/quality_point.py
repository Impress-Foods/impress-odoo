from odoo import api, fields, models


class QualityPoint(models.Model):
    _inherit = "quality.point"

    log_type_id = fields.Many2one(
        "worksheet.log.type",
        string="QC Log Type",
        help="If set, template is resolved from log type configuration",
    )

    worksheet_template_id = fields.Many2one(
        compute="_compute_worksheet_template_id",
        inverse="_inverse_worksheet_template_id",
        store=True,
        readonly=False,
    )

    def _inverse_worksheet_template_id(self):
        pass

    @api.depends("log_type_id", "log_type_id.active_template_id")
    def _compute_worksheet_template_id(self):
        for record in self:
            if record.log_type_id and record.log_type_id.active_template_id:
                record.worksheet_template_id = record.log_type_id.active_template_id
