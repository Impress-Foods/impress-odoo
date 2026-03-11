from odoo import api, models


class MrpCampaignReport(models.AbstractModel):
    _name = "report.mrp_campaign.report_mrp_campaign_document"
    _description = "MRP Campaign Report"

    @api.model
    def _get_report_values(self, docids, data=None):  # pragma: no cover
        docs = self.env["mrp.campaign"].browse(docids)
        return {
            "doc_ids": docs.ids,
            "doc_model": "mrp.campaign",
            "docs": docs,
        }
