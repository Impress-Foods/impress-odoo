import logging

from odoo import _, models
from odoo.exceptions import ValidationError

from odoo.addons.mrp.models.mrp_bom import MrpBomLine
from odoo.addons.product.models.product_product import ProductProduct

_logger = logging.getLogger(__name__)


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def get_factor_to_product(self, product: ProductProduct) -> float:
        self.ensure_one()
        bom_lines: MrpBomLine = self.bom_line_ids.filtered_domain(
            [("product_id", "=", product.id)]
        )

        if len(bom_lines) == 0:
            raise ValidationError(_("Bom has no line with target product"))
        if len(bom_lines) > 1:
            raise ValidationError(_("Bom has more than one line with target product"))
        else:
            return bom_lines.product_qty / self.product_qty
