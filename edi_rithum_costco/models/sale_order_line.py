from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    costco_sku = fields.Char(
        string="Costco SKU",
        readonly=True,
        copy=False,
        help="Costco's own item number for the line (PO107 of the 850). Our "
        "item number is the product's internal reference.",
    )

    def _compute_price_unit(self):
        """Extends sale.order.line._compute_price_unit.

        The price on a Costco line is the one in the 850, which is contractual.
        The standard method recomputes it from the pricelist whenever the
        quantity changes (it treats a price as manual only when it differs from
        ``technical_price_unit``, and both are equal at creation), so a partial
        cancellation or a quantity edit would silently replace it. Costco lines
        are left out; every other line follows the standard path.
        """
        costco_lines = self.filtered("costco_sku")
        return super(SaleOrderLine, self - costco_lines)._compute_price_unit()
