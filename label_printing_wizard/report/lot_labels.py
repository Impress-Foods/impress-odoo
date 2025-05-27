import logging

from odoo import models, _

_logger = logging.getLogger(__name__)


class ReportLotLabel(models.AbstractModel):
    _inherit = "report.stock.label_lot_template_view"

    def _get_report_values(self, docids, data):
        res = super()._get_report_values(docids, data)
        if 'label_product_qty' in self.env.context:
            res['docs'][0]['product_qty'] = self.env.context.get('label_product_qty')
        return res
7