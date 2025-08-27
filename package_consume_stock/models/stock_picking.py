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

    def _pre_action_done_hook(self):
        res = super()._pre_action_done_hook()
        self._handle_new_package()
        return res

    def _handle_new_package(self):
        for picking in self:
            for package in picking.package_ids:
                if not package.material_added and package.package_type_id:
                    package_type = package.package_type_id
                    source_location = (
                        package_type.source_location_id or picking.location_id
                    )
                    product = package_type.packaging_material_id or None

                    if product:
                        existing_line = picking.move_ids.filtered_domain(
                            [("product_id", "=", product.id)]
                        )
                        lot_id = False
                        if existing_line and product.tracking in ["serial", "lot"]:
                            lot_id = existing_line[0].move_line_ids[0].lot_id.id

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
                            }
                        )
                        picking.move_ids.filtered_domain(
                            [("product_id", "=", product.id)]
                        )[0].product_uom_qty += 1

                        package.material_added = True
