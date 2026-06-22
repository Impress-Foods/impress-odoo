from odoo.tests import TransactionCase

from odoo.addons.stock.models.stock_location import StockLocation
from odoo.addons.stock.models.stock_picking import StockPickingType


class TestStockPicking(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stock_loc_id: StockLocation = cls.env.ref("stock.stock_location_stock")  # type: ignore
        cls.cust_loc_id: StockLocation = cls.env.ref("stock.stock_location_customers")  # type: ignore
        cls.picking_type_out: StockPickingType = cls.env.ref("stock.picking_type_out")  # type:ignore

        cls.picking_model = cls.env["stock.picking"]
        cls.move_model = cls.env["stock.move"]
        cls.ml_model = cls.env["stock.move.line"]
        cls.material_model = cls.env["stock.package.material"]

        cls.product = cls.env["product.product"].create(
            {
                "name": "Product",
                "tracking": "none",
                "type": "consu",
                "is_storable": True,
            }
        )
        cls.env["stock.quant"].create(
            {
                "location_id": cls.stock_loc_id.id,
                "product_id": cls.product.id,
                "quantity": 100,
            }
        )
        cls.packaging_material_wo_lot = cls.env["product.product"].create(
            {
                "name": "Package Material Without Lot",
                "tracking": "none",
                "type": "consu",
                "is_storable": True,
            }
        )
        cls.env["stock.quant"].create(
            {
                "location_id": cls.stock_loc_id.id,
                "product_id": cls.packaging_material_wo_lot.id,
                "quantity": 10,
            }
        )
        cls.material_wo_lot = cls.material_model.create(
            {
                "product_id": cls.packaging_material_wo_lot.id,
                "location_id": cls.stock_loc_id.id,
                "quantity": 1.0,
            }
        )

        cls.package_type_wo_lot = cls.env["stock.package.type"].create(
            {
                "name": "Test Package Type without Lot",
                "packaging_material_ids": [(4, cls.material_wo_lot.id, 0)],
            }
        )

        cls.packaging_material_w_lot = cls.env["product.product"].create(
            {
                "name": "Package Material With Lot",
                "tracking": "lot",
                "type": "consu",
                "is_storable": True,
            }
        )

        cls.lot_1 = cls.env["stock.lot"].create(
            {
                "product_id": cls.packaging_material_w_lot.id,
            }
        )
        cls.lot_2 = cls.env["stock.lot"].create(
            {
                "product_id": cls.packaging_material_w_lot.id,
            }
        )

        cls.env["stock.quant"].create(
            {
                "location_id": cls.stock_loc_id.id,
                "product_id": cls.packaging_material_w_lot.id,
                "quantity": 10,
                "lot_id": cls.lot_1.id,
            }
        )
        cls.env["stock.quant"].create(
            {
                "location_id": cls.stock_loc_id.id,
                "product_id": cls.packaging_material_w_lot.id,
                "quantity": 10,
                "lot_id": cls.lot_2.id,
            }
        )

        cls.material_w_lot = cls.material_model.create(
            {
                "product_id": cls.packaging_material_w_lot.id,
                "location_id": cls.stock_loc_id.id,
                "quantity": 1.0,
            }
        )

        cls.package_type_w_lot = cls.env["stock.package.type"].create(
            {
                "name": "Test Package Type with Lot",
                "packaging_material_ids": [(4, cls.material_w_lot.id, 0)],
            }
        )

        cls.package_type_w_multiple = cls.env["stock.package.type"].create(
            {
                "name": "Test package type with multiple material",
                "packaging_material_ids": [
                    (6, 0, [cls.material_w_lot.id, cls.material_wo_lot.id])
                ],
            }
        )

    def test_create_new_package_wo_lot_single_package(self):
        picking = self.env["stock.picking"].create(
            {
                "location_dest_id": self.cust_loc_id.id,
                "location_id": self.stock_loc_id.id,
                "picking_type_id": self.picking_type_out.id,
            }
        )
        move = self.move_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 4,
                "picking_id": picking.id,
                "location_id": self.stock_loc_id.id,
                "location_dest_id": self.cust_loc_id.id,
            }
        )
        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(picking.state, "assigned")

        move_lines = picking.move_line_ids

        self.assertEqual(len(move_lines), 1)
        self.assertEqual(
            move_lines[0].product_id,
            self.product,
            f"Incorrect product in move line, is {move_lines[0].product_id.name}",
        )
        product_move_line = move_lines[0]
        product_move_line.qty_done = 4
        move.picked = True
        picking.action_put_in_pack(package_type_id=self.package_type_wo_lot.id)
        self.assertEqual(
            picking.packages_count,
            1,
            f"Should be 1 package, currently {picking.packages_count}",
        )

        # Line added for the new packaging material
        self.assertEqual(
            len(
                picking.move_line_ids.filtered_domain(
                    [("product_id", "=", self.packaging_material_wo_lot.id)]
                )
            ),
            1,
        )
        self.assertEqual(
            len(
                picking.move_line_ids.filtered_domain(
                    [("product_id", "=", self.product.id)]
                )
            ),
            1,
        )
        # Check if all products are in the same package
        self.assertEqual(len(picking.move_line_ids.mapped("result_package_id")), 1)
        # Check if possible to validate transfer
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_create_new_package_w_lot_single_package(self):
        picking = self.env["stock.picking"].create(
            {
                "location_dest_id": self.cust_loc_id.id,
                "location_id": self.stock_loc_id.id,
                "picking_type_id": self.picking_type_out.id,
            }
        )
        move = self.move_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 4,
                "picking_id": picking.id,
                "location_id": self.stock_loc_id.id,
                "location_dest_id": self.cust_loc_id.id,
            }
        )
        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(picking.state, "assigned")

        move_lines = picking.move_line_ids

        self.assertEqual(len(move_lines), 1)
        self.assertEqual(
            move_lines[0].product_id,
            self.product,
            f"Incorrect product in move line, is {move_lines[0].product_id.name}",
        )
        product_move_line = move_lines[0]
        product_move_line.qty_done = 4  # type: ignore

        move.picked = True
        picking.action_put_in_pack(package_type_id=self.package_type_w_lot.id)
        self.assertEqual(
            picking.packages_count,
            1,
            f"Should be 1 package, currently {picking.packages_count}",
        )

        # Line added for the new packaging material
        self.assertEqual(
            len(
                picking.move_line_ids.filtered_domain(
                    [("product_id", "=", self.packaging_material_w_lot.id)]
                )
            ),
            1,
        )
        self.assertEqual(
            len(
                picking.move_line_ids.filtered_domain(
                    [("product_id", "=", self.product.id)]
                )
            ),
            1,
        )

        # Check if all products are in the same package
        self.assertEqual(len(picking.move_line_ids.mapped("result_package_id")), 1)

        # Check if possible to validate transfer
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_create_new_package_wo_lot_multiple_packages(self):
        picking = self.env["stock.picking"].create(
            {
                "location_dest_id": self.cust_loc_id.id,
                "location_id": self.stock_loc_id.id,
                "picking_type_id": self.picking_type_out.id,
            }
        )
        self.move_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 4,
                "picking_id": picking.id,
                "location_id": self.stock_loc_id.id,
                "location_dest_id": self.cust_loc_id.id,
            }
        )

        picking.action_confirm()
        picking.action_assign()
        product_moves = picking.move_ids.filtered_domain(
            [("product_id", "=", self.product.id)]
        )
        self.assertEqual(len(product_moves), 1)

        product_ml = product_moves[0].move_line_ids[0]
        product_ml.quantity = 2.0
        product_ml.picked = True

        picking.action_put_in_pack(package_type_id=self.package_type_wo_lot.id)

        self.assertEqual(picking.packages_count, 1)
        packaging_move = picking.move_ids.filtered_domain(
            [("product_id", "=", self.packaging_material_wo_lot.id)]
        )
        self.assertEqual(len(packaging_move), 1)
        self.assertEqual(packaging_move.quantity, 1.0)

        new_product_ml = product_ml.copy()
        new_product_ml.result_package_id = False
        new_product_ml.quantity = 2.0
        new_product_ml.picked = True

        picking.action_put_in_pack(package_type_id=self.package_type_wo_lot.id)

        packages = self.env["stock.package"].search([])

        packages = packages.filtered(
            lambda r: picking.id in [p.id for p in r.picking_ids]
        )
        self.assertEqual(len(packages), 2)

        packaging_move = picking.move_ids.filtered_domain(
            [("product_id", "=", self.packaging_material_wo_lot.id)]
        )
        self.assertEqual(len(packaging_move), 1)
        self.assertEqual(packaging_move.quantity, 2.0)

    def test_create_new_package_w_lot_multiple_packages(self):
        PRODUCT_QTY = 4
        picking = self.env["stock.picking"].create(
            {
                "location_dest_id": self.cust_loc_id.id,
                "location_id": self.stock_loc_id.id,
                "picking_type_id": self.picking_type_out.id,
            }
        )
        move = self.move_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": PRODUCT_QTY,
                "picking_id": picking.id,
                "location_id": self.stock_loc_id.id,
                "location_dest_id": self.cust_loc_id.id,
            }
        )

        picking.action_confirm()
        picking.action_assign()
        product_moves = picking.move_ids.filtered_domain(
            [("product_id", "=", self.product.id)]
        )
        self.assertEqual(len(product_moves), 1)

        product_ml = product_moves[0].move_line_ids[0]
        product_ml.quantity = 2.0
        product_ml.picked = True

        picking.action_put_in_pack(package_type_id=self.package_type_w_lot.id)

        self.assertEqual(picking.packages_count, 1)
        packaging_move = picking.move_ids.filtered_domain(
            [("product_id", "=", self.packaging_material_w_lot.id)]
        )
        self.assertEqual(len(packaging_move), 1)
        self.assertEqual(packaging_move.quantity, 1.0)
        self.assertTrue(packaging_move.move_line_ids[0].lot_id)

        new_product_ml = product_ml.copy()
        new_product_ml.result_package_id = False
        new_product_ml.quantity = 2.0
        new_product_ml.picked = True

        picking.action_put_in_pack(package_type_id=self.package_type_w_lot.id)

        packages = self.env["stock.package"].search([])

        packages = packages.filtered(
            lambda r: picking.id in [p.id for p in r.picking_ids]
        )

        self.assertEqual(len(packages), 2)
        packaging_move = picking.move_ids.filtered_domain(
            [("product_id", "=", self.packaging_material_w_lot.id)]
        )
        self.assertEqual(len(packaging_move), 1)
        self.assertEqual(packaging_move.quantity, 2.0)
        self.assertEqual(move.quantity, PRODUCT_QTY)

    def test_create_new_package_w_multiple_material(self):
        PRODUCT_QTY = 4
        picking = self.env["stock.picking"].create(
            {
                "location_dest_id": self.cust_loc_id.id,
                "location_id": self.stock_loc_id.id,
                "picking_type_id": self.picking_type_out.id,
            }
        )
        move = self.move_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": PRODUCT_QTY,
                "picking_id": picking.id,
                "location_id": self.stock_loc_id.id,
                "location_dest_id": self.cust_loc_id.id,
            }
        )
        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(picking.state, "assigned")

        move_lines = picking.move_line_ids

        self.assertEqual(len(move_lines), 1)
        self.assertEqual(
            move_lines[0].product_id,
            self.product,
            f"Incorrect product in move line, is {move_lines[0].product_id.name}",
        )
        product_move_line = move_lines[0]
        product_move_line.qty_done = 4.0
        product_move_line.picked = True
        picking.action_put_in_pack(package_type_id=self.package_type_w_multiple.id)
        self.assertEqual(
            picking.packages_count,
            1,
            f"Should be 1 package, currently {picking.packages_count}",
        )

        # Line added for the new packaging material
        self.assertEqual(
            len(
                picking.move_line_ids.filtered_domain(
                    [("product_id", "=", self.packaging_material_wo_lot.id)]
                )
            ),
            1,
        )
        self.assertEqual(
            len(
                picking.move_line_ids.filtered_domain(
                    [("product_id", "=", self.packaging_material_w_lot.id)]
                )
            ),
            1,
        )

        self.assertEqual(
            len(
                picking.move_line_ids.filtered_domain(
                    [("product_id", "=", self.product.id)]
                )
            ),
            1,
        )

        # Check if all products are in the same package
        self.assertEqual(len(picking.move_line_ids.mapped("result_package_id")), 1)
        picking.move_line_ids.filtered_domain(
            [("product_id", "=", self.packaging_material_w_lot.id)]
        ).lot_id = self.lot_1.id
        self.assertEqual(move.quantity, PRODUCT_QTY)
        # Check if possible to validate transfer
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_wizard_path_move_line_survives(self):
        """Regression test for default_move_line_ids context bug.

        When the packaging move is created via stock.move.create(), the ORM
        picks up default_move_line_ids from the wizard context and silently
        reassigns the product's move line to the new packaging move.
        """
        # Use a picking type that forces the wizard
        wizard_type = self.picking_type_out.copy()
        wizard_type.set_package_type = True

        picking = self.env["stock.picking"].create(
            {
                "location_dest_id": self.cust_loc_id.id,
                "location_id": self.stock_loc_id.id,
                "picking_type_id": wizard_type.id,
            }
        )
        self.move_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 2,
                "picking_id": picking.id,
                "location_id": self.stock_loc_id.id,
                "location_dest_id": self.cust_loc_id.id,
            }
        )
        picking.action_confirm()
        picking.action_assign()
        move_line = picking.move_line_ids[0]
        move_line.qty_done = 2.0
        move_line.picked = True
        original_move_id = move_line.move_id.id
        original_product_id = move_line.product_id.id

        # First call: triggers the wizard (no package_type_id)
        wizard_action = move_line.action_put_in_pack()
        self.assertTrue(wizard_action, "Wizard should be returned")
        self.assertEqual(wizard_action.get("type"), "ir.actions.act_window")

        # Simulate wizard submission: context carries default_move_line_ids
        ctx = {
            **self.env.context,
            "from_package_wizard": True,
            "all_move_line_ids": [move_line.id],
            "default_move_line_ids": [move_line.id],
            "default_location_dest_id": move_line.location_dest_id.id,
            "picking_ids": [picking.id],
        }
        move_line.with_context(ctx).action_put_in_pack(  # pylint: disable=context-overridden
            package_type_id=self.package_type_wo_lot.id
        )

        # The original move line must NOT have been hijacked by the packaging move
        self.assertEqual(
            move_line.move_id.id,
            original_move_id,
            "Product move line was reassigned to packaging move",
        )
        self.assertEqual(
            move_line.product_id.id,
            original_product_id,
            "Product move line's product changed",
        )
        # Packaging move line should exist separately
        packaging_lines = picking.move_line_ids.filtered_domain(
            [("product_id", "=", self.packaging_material_wo_lot.id)]
        )
        self.assertEqual(
            len(packaging_lines),
            1,
            "Packaging material line should exist separately",
        )
