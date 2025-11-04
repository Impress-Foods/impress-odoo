import logging

from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from odoo.addons.stock.models.stock_location import Location
from odoo.addons.stock.models.stock_picking import PickingType

_logger = logging.getLogger(__name__)


class TestStockPicking(TransactionCase):
    def setUp(self):
        super().setUp()
        self.stock_loc_id: Location = self.env.ref("stock.stock_location_stock")  # type: ignore
        self.cust_loc_id: Location = self.env.ref("stock.stock_location_customers")  # type: ignore
        self.picking_type_out: PickingType = self.env.ref("stock.picking_type_out")  # type:ignore

        self.picking_model = self.env["stock.picking"]
        self.move_model = self.env["stock.move"]
        self.ml_model = self.env["stock.move.line"]

        self.product = self.env["product.product"].create(
            {
                "name": "Product",
                "tracking": "none",
                "type": "product",
            }
        )
        self.env["stock.quant"].create(
            {
                "location_id": self.stock_loc_id.id,
                "product_id": self.product.id,
                "quantity": 100,
            }
        )
        self.packaging_material_wo_lot = self.env["product.product"].create(
            {
                "name": "Package Material Without Lot",
                "tracking": "none",
                "type": "product",
            }
        )
        self.env["stock.quant"].create(
            {
                "location_id": self.stock_loc_id.id,
                "product_id": self.packaging_material_wo_lot.id,
                "quantity": 10,
            }
        )
        self.package_type_wo_lot = self.env["stock.package.type"].create(
            {
                "name": "Test Package Type without Lot",
                "packaging_material_id": self.packaging_material_wo_lot.id,
            }
        )
        self.packaging_material_w_lot = self.env["product.product"].create(
            {
                "name": "Package Material With Lot",
                "tracking": "lot",
                "type": "product",
            }
        )

        self.lot_1 = self.env["stock.lot"].create(
            {
                "product_id": self.packaging_material_w_lot.id,
            }
        )
        self.lot_2 = self.env["stock.lot"].create(
            {
                "product_id": self.packaging_material_w_lot.id,
            }
        )

        self.env["stock.quant"].create(
            {
                "location_id": self.stock_loc_id.id,
                "product_id": self.packaging_material_w_lot.id,
                "quantity": 10,
                "lot_id": self.lot_1.id,
            }
        )
        self.env["stock.quant"].create(
            {
                "location_id": self.stock_loc_id.id,
                "product_id": self.packaging_material_w_lot.id,
                "quantity": 10,
                "lot_id": self.lot_2.id,
            }
        )
        self.package_type_w_lot = self.env["stock.package.type"].create(
            {
                "name": "Test Package Type with Lot",
                "packaging_material_id": self.packaging_material_w_lot.id,
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
        self.move_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 4,
                "picking_id": picking.id,
                "location_id": self.stock_loc_id.id,
                "location_dest_id": self.cust_loc_id.id,
                "name": "product move",
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

        self.env["choose.delivery.package"].create(
            {
                "picking_id": picking.id,
                "delivery_package_type_id": self.package_type_wo_lot.id,
            }
        ).action_put_in_pack()
        self.assertEqual(
            len(picking.package_ids),
            1,
            f"Should be 1 package, currently {len(picking.package_ids)}",
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
        self.move_model.create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 4,
                "picking_id": picking.id,
                "location_id": self.stock_loc_id.id,
                "location_dest_id": self.cust_loc_id.id,
                "name": "product move",
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

        self.env["choose.delivery.package"].create(
            {
                "picking_id": picking.id,
                "delivery_package_type_id": self.package_type_w_lot.id,
            }
        ).action_put_in_pack()
        self.assertEqual(
            len(picking.package_ids),
            1,
            f"Should be 1 package, currently {len(picking.package_ids)}",
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
        # Should not be able to validate transfer without package lot
        with self.assertRaises(UserError):  # type: ignore
            picking.button_validate()

        picking.move_line_ids.filtered_domain(
            [("product_id", "=", self.packaging_material_w_lot.id)]
        ).lot_id = self.lot_1.id

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
                "name": "product move",
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

        self.env["choose.delivery.package"].create(
            {
                "picking_id": picking.id,
                "delivery_package_type_id": self.package_type_wo_lot.id,
            }
        ).action_put_in_pack()

        self.assertEqual(len(picking.package_ids), 1)
        packaging_move = picking.move_ids.filtered_domain(
            [("product_id", "=", self.packaging_material_wo_lot.id)]
        )
        self.assertEqual(len(packaging_move), 1)
        self.assertEqual(packaging_move.quantity, 1.0)

        new_product_ml = product_ml.copy()
        new_product_ml.result_package_id = False
        new_product_ml.quantity = 2.0
        new_product_ml.picked = True

        self.env["choose.delivery.package"].create(
            {
                "picking_id": picking.id,
                "delivery_package_type_id": self.package_type_wo_lot.id,
            }
        ).action_put_in_pack()

        self.assertEqual(len(picking.package_ids), 2)
        packaging_move = picking.move_ids.filtered_domain(
            [("product_id", "=", self.packaging_material_wo_lot.id)]
        )
        self.assertEqual(len(packaging_move), 1)
        self.assertEqual(packaging_move.quantity, 2.0)

    def test_create_new_package_w_lot_multiple_packages(self):
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
                "name": "product move",
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

        self.env["choose.delivery.package"].create(
            {
                "picking_id": picking.id,
                "delivery_package_type_id": self.package_type_w_lot.id,
            }
        ).action_put_in_pack()

        self.assertEqual(len(picking.package_ids), 1)
        packaging_move = picking.move_ids.filtered_domain(
            [("product_id", "=", self.packaging_material_w_lot.id)]
        )
        packaging_move.move_line_ids[0].lot_id = self.lot_2.id
        self.assertEqual(len(packaging_move), 1)
        self.assertEqual(packaging_move.quantity, 1.0)

        new_product_ml = product_ml.copy()
        new_product_ml.result_package_id = False
        new_product_ml.quantity = 2.0
        new_product_ml.picked = True

        self.env["choose.delivery.package"].create(
            {
                "picking_id": picking.id,
                "delivery_package_type_id": self.package_type_w_lot.id,
            }
        ).action_put_in_pack()

        self.assertEqual(len(picking.package_ids), 2)
        packaging_move = picking.move_ids.filtered_domain(
            [("product_id", "=", self.packaging_material_w_lot.id)]
        )
        self.assertEqual(len(packaging_move), 1)
        self.assertEqual(packaging_move.quantity, 2.0)

        # Check if all packages are in the same lot
        self.assertEqual(
            len(set([ml.lot_id for ml in packaging_move.move_line_ids])), 1
        )
