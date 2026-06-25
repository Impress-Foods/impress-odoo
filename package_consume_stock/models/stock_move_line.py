from odoo import models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _post_put_in_pack_hook(self, package):
        res = super()._post_put_in_pack_hook(package)
        if (
            package
            and not package.material_added
            and package.package_type_id.packaging_material_ids
        ):
            for material_line in package.package_type_id.packaging_material_ids:
                material_line._make_packaging_material_move(self.picking_id, package)
            package.material_added = True
        return res
