from odoo import fields, models
from odoo.exceptions import ValidationError

from odoo.addons.stock.models.stock_move import StockMove
from odoo.addons.stock.models.stock_package import StockPackage
from odoo.addons.stock.models.stock_picking import StockPicking


class PackageMaterial(models.Model):
    _name = "stock.package.material"
    _description = "Material to be added to a package"

    product_id = fields.Many2one("product.product", required=True)
    quantity = fields.Float(default=0)
    location_id = fields.Many2one("stock.location")

    def _get_packaging_material_move(self, picking: StockPicking) -> StockMove | None:
        self.ensure_one()
        picking.ensure_one()

        packaging_move = picking.move_ids.filtered_domain(
            [("product_id", "=", self.product_id.id)]
        )

        if not packaging_move:
            clean_context = dict(self.env.context)
            clean_context.pop("default_move_line_ids", None)

            packaging_move = (
                self.env["stock.move"]
                .with_context(default_move_line_ids=False)
                .create(
                    {
                        "picking_id": picking.id,
                        "product_id": self.product_id.id,
                        "product_uom_qty": 0,
                        "product_uom": self.product_id.uom_id.id,
                        "location_id": self.location_id.id,
                        "location_dest_id": picking.location_dest_id.id,
                        "company_id": picking.company_id.id,
                    }
                )
            )
            packaging_move._action_confirm(merge=False)
        else:
            packaging_move = packaging_move[0]
        return packaging_move

    def _make_packaging_material_move(
        self, picking: StockPicking, package: StockPackage
    ) -> None:
        self.ensure_one()
        move = self._get_packaging_material_move(picking)
        if not move:
            raise ValidationError(
                self.env._(
                    "Could not get or create packaging move for %(mat)s in %(picking)s",
                    mat=self.product_id.display_name,
                    picking=picking.display_name,
                )
            )

        move.with_context(do_not_unreserve=True).product_uom_qty += self.quantity
        move._action_assign(force_qty=self.quantity)

        for ml in move.move_line_ids.filtered(lambda line: not line.result_package_id):
            ml.result_package_id = package.id
            ml.picked = True
