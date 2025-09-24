import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _post_put_in_pack_hook(self, package):
        res = super()._post_put_in_pack_hook(package)
        self._handle_new_package()
        return res

    def _handle_new_package(self):
        for move_line in self:
            picking = move_line.picking_id
            for package in move_line.result_package_id:
                if not package.material_added and package.package_type_id:
                    package_type = package.package_type_id

                    source_location = (
                        package_type.source_location_id or picking.location_id
                    )
                    product = package_type.packaging_material_id or None

                    if product:
                        # Ensure there is a corresponding move
                        # for the packaging material
                        packaging_move = picking.move_ids.filtered_domain(
                            [("product_id", "=", product.id)]
                        )[:1]

                        lot_id = False

                        if not packaging_move:
                            packaging_move = self.env["stock.move"].create(
                                {
                                    "picking_id": picking.id,
                                    "product_id": product.id,
                                    "product_uom_qty": 0,
                                    "quantity": 0,
                                    "location_id": source_location.id,
                                    "location_dest_id": picking.location_dest_id.id,
                                    "company_id": picking.company_id.id,
                                    "move_line_ids": False,
                                }
                            )

                        else:
                            packaging_move = packaging_move[0]
                            if product.tracking in ["serial", "lot"]:
                                if packaging_move.move_line_ids:
                                    lot_id = packaging_move.move_line_ids[0].lot_id.id

                        self.env["stock.move.line"].create(
                            {
                                "picking_id": picking.id,
                                "company_id": picking.company_id.id,
                                "reference": picking.name,
                                "location_id": source_location.id,
                                "location_dest_id": picking.location_dest_id.id,
                                "result_package_id": package.id,
                                "product_id": product.id,
                                "quantity": 1,
                                "qty_done": 1,
                                "lot_id": lot_id,
                                "move_id": packaging_move.id,
                            }
                        )

                        packaging_move.product_uom_qty += 1
                        package.material_added = True
