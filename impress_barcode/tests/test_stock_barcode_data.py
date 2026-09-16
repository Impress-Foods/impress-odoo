from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockBarcodeData(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.product = cls.env["product.product"].create(
            {"name": "Barcode Test Product", "is_storable": True}
        )
        cls.picking = cls.env["stock.picking"].create(
            {
                "origin": "SO-BARCODE-TEST",
                "picking_type_id": cls.warehouse.out_type_id.id,
                "location_id": cls.warehouse.lot_stock_id.id,
                "location_dest_id": cls.customer_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": 3,
                            "location_id": cls.warehouse.lot_stock_id.id,
                            "location_dest_id": cls.customer_location.id,
                        }
                    )
                ],
            }
        )

    def test_stock_move_fields(self):
        """The barcode cache must carry every `stock.move` field the JS reads."""
        data = self.picking._get_stock_barcode_data()
        move = data["records"]["stock.move"][0]
        for field in [
            "product_id",
            "location_id",
            "location_dest_id",
            "product_uom_qty",
            "product_uom",
            "bom_line_id",
            "description_picking",
        ]:
            self.assertIn(
                field, move, f"stock.move field {field} missing from barcode data"
            )

    def test_origin_field(self):
        """The picking `origin` is added for the barcode title."""
        data = self.picking._get_stock_barcode_data()
        picking = data["records"]["stock.picking"][0]
        self.assertEqual(picking["origin"], "SO-BARCODE-TEST")
