from odoo import _, models
from odoo.exceptions import ValidationError

from odoo.addons.mrp.models.mrp_bom import MrpBomLine
from odoo.addons.product.models.product_product import ProductProduct


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
            line = bom_lines[0]
            # Normalize parent quantity to the product's reference UoM
            parent_ref_qty = self.product_uom_id._compute_quantity(
                self.product_qty, self.product_tmpl_id.uom_id
            )
            # Normalize component quantity to its reference UoM
            component_ref_qty = line.product_uom_id._compute_quantity(
                line.product_qty, line.product_id.uom_id
            )
            return component_ref_qty / parent_ref_qty
