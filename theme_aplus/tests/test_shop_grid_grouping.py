# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.theme_aplus.controllers.main import ThemeAPlusWebsiteSale
from odoo.addons.website_sale.controllers.main import TableCompute


@tagged("post_install", "-at_install")
class TestShopGridGrouping(TransactionCase):
    """Check the shop grid grouping by public category.

    ``ThemeAPlusWebsiteSale._group_bins_by_category`` only depends on the values
    it is handed, so it can be exercised without going through the website
    routing. The input grid is built with core's own ``TableCompute``: that way
    the test also guards the contract with core's packing.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ppg = 20
        cls.ppr = 4

    def _make_category(self, name, sequence):
        return self.env["product.public.category"].create(
            {"name": name, "sequence": sequence}
        )

    def _make_product(self, name, category=None, size_x=1, size_y=1):
        values = {
            "name": name,
            "website_size_x": size_x,
            "website_size_y": size_y,
        }
        if category is not None:
            values["public_categ_ids"] = [Command.set(category.ids)]
        return self.env["product.template"].create(values)

    def _group(self, products):
        values = {
            "bins": TableCompute().process(products, self.ppg, self.ppr),
            "ppg": self.ppg,
            "ppr": self.ppr,
        }
        return ThemeAPlusWebsiteSale._group_bins_by_category(values)

    @staticmethod
    def _cells(bins):
        return [cell for row in bins for cell in row if cell]

    def test_products_are_grouped_by_category(self):
        """Products sharing a category end up contiguous, by category order."""
        drinks = self._make_category("Drinks", 10)
        shots = self._make_category("Shots", 20)
        raspberry = self._make_product("Raspberry", drinks)
        mango = self._make_product("Mango", drinks)
        ginger = self._make_product("Ginger", shots)

        # Deliberately interleaved creation order.
        bins = self._group(ginger + raspberry + mango)

        self.assertEqual(
            [cell["product"] for cell in self._cells(bins)],
            [raspberry, mango, ginger],
        )

    def test_header_is_set_on_first_product_of_each_category(self):
        """Only the first product of a category carries the header."""
        drinks = self._make_category("Drinks", 10)
        shots = self._make_category("Shots", 20)
        raspberry = self._make_product("Raspberry", drinks)
        mango = self._make_product("Mango", drinks)
        ginger = self._make_product("Ginger", shots)

        cells = self._cells(self._group(ginger + raspberry + mango))

        self.assertEqual(cells[0]["group_header"], "Drinks")
        self.assertNotIn("group_header", cells[1])
        self.assertEqual(cells[2]["group_header"], "Shots")

    def test_single_category_has_no_header(self):
        """A grid with a single category has nothing to separate."""
        drinks = self._make_category("Drinks", 10)
        bins = self._group(
            self._make_product("Raspberry", drinks)
            + self._make_product("Mango", drinks)
        )

        self.assertFalse(
            [cell for cell in self._cells(bins) if cell.get("group_header")]
        )

    def test_products_without_category_are_grouped_last(self):
        """Uncategorised products must not be dropped, nor get a header."""
        drinks = self._make_category("Drinks", 10)
        shots = self._make_category("Shots", 20)
        uncategorised = self._make_product("Uncategorised")
        raspberry = self._make_product("Raspberry", drinks)
        ginger = self._make_product("Ginger", shots)

        cells = self._cells(self._group(uncategorised + raspberry + ginger))

        self.assertEqual(
            [cell["product"] for cell in cells],
            [raspberry, ginger, uncategorised],
        )
        self.assertNotIn("group_header", cells[-1])

    def test_product_spans_are_preserved(self):
        """Regrouping must not discard the ``x``/``y`` spans packed by core."""
        drinks = self._make_category("Drinks", 10)
        shots = self._make_category("Shots", 20)
        wide = self._make_product("Wide", drinks, size_x=2)
        ginger = self._make_product("Ginger", shots)

        cells = self._cells(self._group(ginger + wide))

        self.assertEqual([cell["product"] for cell in cells], [wide, ginger])
        self.assertEqual(cells[0]["x"], 2)
