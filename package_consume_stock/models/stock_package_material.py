from odoo import fields, models

from odoo.addons.stock.models.stock_lot import StockLot
from odoo.addons.stock.models.stock_move import StockMove
from odoo.addons.stock.models.stock_picking import StockPicking


class PackageMaterial(models.Model):
    _name = "stock.package.material"
    _description = "Material to be added to a package"

    product_id = fields.Many2one("product.product", required=True)
    quantity = fields.Float(default=0)
    location_id = fields.Many2one("stock.location")

    def _get_packaging_material_move(self, picking: StockPicking) -> StockMove | None:
        self.ensure_one()

        if len(picking) != 1:
            return None

        packaging_move = picking.move_ids.filtered_domain(
            [("product_id", "=", self.product_id.id)]
        )[:1]

        if not packaging_move:
            packaging_move = self.env["stock.move"].create(
                {
                    "picking_id": picking.id,
                    "name": f"Packaging: {self.product_id.display_name}",
                    "product_id": self.product_id.id,
                    "product_uom_qty": 0,
                    "product_uom": self.product_id.uom_id.id,
                    "location_id": self.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                    "company_id": picking.company_id.id,
                }
            )
        else:
            packaging_move = packaging_move[0]

        return packaging_move

    def _get_packaging_lot(self, picking: StockPicking) -> StockLot | bool:
        existing_line = picking.move_ids.filtered_domain(
            [("product_id", "=", self.product_id.id)]
        )
        lot_id = False
        if existing_line and self.product_id.tracking in ["serial", "lot"]:
            line = existing_line[0]
            if line.move_line_ids:
                lot_id = line.move_line_ids[0].lot_id.id

        return lot_id
