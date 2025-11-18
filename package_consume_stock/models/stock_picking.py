import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def write(self, vals):
        res = super().write(vals)
        self._handle_new_package()
        return res

    def _post_put_in_pack_hook(self, package):
        res = super()._post_put_in_pack_hook(package)
        self._handle_new_package()
        return res

    def _handle_new_package(self):
        for picking in self:
            for package in picking.package_ids:
                if (
                    not package.material_added
                    and package.package_type_id.has_packaging_material
                ):
                    for material in package.package_type_id.packaging_material_ids:
                        source_location = material.location_id or picking.location_id

                        lot_id = material._get_packaging_lot(picking)

                        packaging_move = material._get_packaging_material_move(picking)

                        if not packaging_move:
                            continue

                        self.env["stock.move.line"].create(
                            {
                                "picking_id": picking.id,
                                "company_id": picking.company_id.id,
                                "reference": picking.name,
                                "location_id": source_location.id,
                                "location_dest_id": picking.location_dest_id.id,
                                "result_package_id": package.id,
                                "product_id": material.product_id.id,
                                "quantity": material.quantity,
                                "qty_done": material.quantity,
                                "lot_id": lot_id,
                                "move_id": packaging_move.id,
                            }
                        )
                        packaging_move.product_uom_qty += material.quantity
                        package.material_added = True
