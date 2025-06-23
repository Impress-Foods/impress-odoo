import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _post_put_in_pack_hook(self, package_id):
        res = super()._post_put_in_pack_hook(package_id)

        if res.package_type_id:
            package_type = res.package_type_id
            source_location = package_type.source_location_id or self.location_id
            product = package_type.packaging_material_id or None

            if product:
                self.env["stock.move.line"].create(
                    {
                        "picking_id": self.id,
                        "company_id": self.company_id.id,
                        "reference": self.name,
                        "location_id": source_location.id,
                        "location_dest_id": self.location_dest_id.id,
                        "result_package_id": res.id,
                        "product_id": product.id,
                        "quantity": 1,
                        "qty_done": 1,
                    }
                )
                self.move_ids.filtered_domain([("product_id", "=", product.id)])[
                    0
                ].product_uom_qty += 1

        return res
