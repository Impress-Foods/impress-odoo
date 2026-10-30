from odoo import api, fields, models

from odoo.addons.edi_core_oca.models.edi_backend import EDIBackend
from odoo.addons.sale.models.sale_order_line import SaleOrderLine


class EdiRithumCostcoProduct(models.Model):
    """A product we report to Costco, with the SKU Costco knows it by."""

    _name = "edi.rithum.costco.product"
    _description = "Costco Product"
    _rec_name = "product_id"
    _order = "product_id"

    backend_id = fields.Many2one(
        "edi.backend", string="Backend", required=True, index=True, ondelete="cascade"
    )
    product_id = fields.Many2one(
        "product.product", required=True, index=True, ondelete="cascade"
    )
    costco_sku = fields.Char(
        string="Costco SKU",
        required=True,
        help="Costco's own item number for the product (LIN05 of the 846).",
    )
    active = fields.Boolean(
        default=True,
        help="Untick to stop reporting the product in the inventory.",
    )
    discontinued_on = fields.Date(
        help="The date replenishment stops. It is reported with the stock and "
        "must stay on every update until the product runs out.",
    )

    _backend_product_unique = models.Constraint(
        "UNIQUE(backend_id, product_id)",
        "A product can be bound to a backend only once.",
    )

    @api.model
    def bind_order_lines(self, backend: EDIBackend, lines: SaleOrderLine) -> None:
        """Bind the products of Costco order lines, or refresh their SKU."""
        wanted = {
            line.product_id: line.costco_sku
            for line in lines.filtered(lambda line: line.costco_sku)
        }
        existing = self.with_context(active_test=False).search(
            [
                ("backend_id", "=", backend.id),
                ("product_id", "in", [product.id for product in wanted]),
            ]
        )
        bound = {binding.product_id: binding for binding in existing}
        for product, sku in wanted.items():
            if product not in bound:
                self.create(
                    {
                        "backend_id": backend.id,
                        "product_id": product.id,
                        "costco_sku": sku,
                    }
                )
            elif bound[product].costco_sku != sku:
                bound[product].costco_sku = sku
