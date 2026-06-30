from odoo import models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _should_display_put_in_pack_wizard(
        self, package_id, package_type_id, package_name, from_package_wizard
    ):
        if self.env.context.get("barcode_view"):
            if from_package_wizard:
                return False
            define_package_type = self._should_set_package()
            return (
                define_package_type
                and not package_id
                and not package_type_id
                and not package_name
            )
        return super()._should_display_put_in_pack_wizard(
            package_id, package_type_id, package_name, from_package_wizard
        )

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
