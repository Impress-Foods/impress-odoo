from odoo import _, api, fields, models


class BaseLogReport(models.AbstractModel):
    _name = "report.base.log.report"
    _description = "Base Log Report Logic"

    def _get_report_values(self, docids, data=None):
        return {
            "report_date": fields.Date.today(),
            "company": self.env.company,
            "doc_ids": docids,
        }


class ReportHppLog(models.AbstractModel):
    _name = "report.impress_quality_logs.report_hpp_log"
    _inherit = "report.base.log.report"
    _description = "HPP Log Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["hpp.log"].browse(docids)

        report_values = super()._get_report_values(docids, data)
        total_produced = sum(docs.mapped("qty_produced"))
        report_values.update(
            {
                "doc_model": "hpp.log",
                "docs": docs,
                "total_produced_in_batch": total_produced,
                "doc_name": _("HPP log"),
            }
        )

        return report_values


class ReportMetalLog(models.AbstractModel):
    _name = "report.impress_quality_logs.report_metal_log"
    _inherit = "report.base.log.report"
    _description = "Metal Log Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["metal.log"].browse(docids)
        report_values = super()._get_report_values(docids, data)

        report_values.update(
            {
                "doc_model": "metal.log",
                "docs": docs,
                "doc_name": _("Metal log"),
            }
        )

        return report_values


class ReportXRayLog(models.AbstractModel):
    _name = "report.impress_quality_logs.report_xray_log"
    _inherit = "report.base.log.report"
    _description = "X-Ray Log Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["x_ray.log"].browse(docids)

        report_values = super()._get_report_values(docids, data)
        report_values.update(
            {
                "doc_model": "x_ray.log",
                "docs": docs,
                "doc_name": _("X-Ray log"),
            }
        )

        return report_values


class ReportweightLog(models.AbstractModel):
    _name = "report.impress_quality_logs.report_weight_log"
    _inherit = "report.base.log.report"
    _description = "weight Log Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        # Get the records for the report
        docs = self.env["weight.log"].browse(docids)

        report_values = super()._get_report_values(docids, data)

        report_values.update(
            {
                "doc_model": "weight.log",
                "docs": docs,
                "doc_name": _("weight log"),
            }
        )

        return report_values


class ReportCodingLog(models.AbstractModel):
    _name = "report.impress_quality_logs.report_coding_log"
    _inherit = "report.base.log.report"
    _description = "Coding Log Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        # Get the records for the report
        docs = self.env["coding.log"].browse(docids)

        report_values = super()._get_report_values(docids, data)

        report_values.update(
            {
                "doc_model": "coding.log",
                "docs": docs,
                "doc_name": _("Coding log"),
            }
        )

        return report_values
