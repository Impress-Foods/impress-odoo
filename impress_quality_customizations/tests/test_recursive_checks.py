# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.fields import Command
from odoo.tests.common import TransactionCase

from odoo.addons.mrp.models.mrp_bom import MrpBom
from odoo.addons.mrp.models.mrp_production import MrpProduction
from odoo.addons.quality.models.quality import QualityCheck
from odoo.addons.stock.models.stock_lot import StockLot


class TestRecursiveQualityChecks(TransactionCase):
    """The lot's checks, and next to them the checks of its production tree."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Both lot buttons, and the count behind them, are quality-group fields.
        cls.env.user.group_ids |= cls.env.ref("quality.group_quality_user")
        cls.picking_type_manu = cls.env["stock.picking.type"].search(
            [("code", "=", "mrp_operation")], limit=1
        )
        cls.picking_type_in = cls.env["stock.picking.type"].search(
            [("code", "=", "incoming")], limit=1
        )
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.component = cls.env["product.product"].create(
            {"name": "Recursive Component", "is_storable": True, "tracking": "serial"}
        )
        cls.finished = cls.env["product.product"].create(
            {"name": "Recursive Finished", "is_storable": True, "tracking": "serial"}
        )
        cls.bom = cls._create_bom(cls.finished, cls.component)

    @classmethod
    def _create_bom(cls, product, component) -> MrpBom:
        return cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_id": product.id,
                "product_qty": 1.0,
                "bom_line_ids": [
                    Command.create({"product_id": component.id, "product_qty": 1.0})
                ],
            }
        )

    def _create_lot(self, product, name: str) -> StockLot:
        return self.env["stock.lot"].create({"name": name, "product_id": product.id})

    def _create_production(self, product, lot=None, bom=None) -> MrpProduction:
        """A confirmed order stating the lot it produces, as an order would."""
        values = {
            "product_id": product.id,
            "product_qty": 1.0,
            "picking_type_id": self.picking_type_manu.id,
        }
        if bom:
            values["bom_id"] = bom.id
        production = self.env["mrp.production"].create(values)
        if lot:
            production.lot_producing_ids = [Command.set(lot.ids)]
        production.action_confirm()
        return production

    def _receive(self, product, lot):
        """A transfer of the lot, so the picking branch has something to find."""
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_in.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1.0,
                            "product_uom": product.uom_id.id,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                ],
            }
        )
        move = picking.move_ids
        move._set_quantity_done(1.0)
        move.move_line_ids.lot_id = lot
        return picking

    def _create_check(self, **values) -> QualityCheck:
        return self.env["quality.check"].create({"quality_state": "pass", **values})

    def _own_checks(self, lot) -> QualityCheck:
        """What the core lot button shows: the checks of this lot alone."""
        return self.env["quality.check"].search(lot._get_quality_check_domain(lot))

    def _tree_checks(self, lot) -> QualityCheck:
        return self.env["quality.check"].search(
            lot._get_recursive_quality_check_domain()
        )

    def _build_tree(self) -> dict:
        """A component lot made by one order and consumed by the next."""
        lot_component = self._create_lot(self.component, "REC-TREE-COMPONENT")
        lot_finished = self._create_lot(self.finished, "REC-TREE-FINISHED")
        component_production = self._create_production(
            self.component, lot=lot_component
        )
        self.env["stock.quant"]._update_available_quantity(
            self.component,
            component_production.location_src_id,
            1.0,
            lot_id=lot_component,
        )
        finished_production = self._create_production(
            self.finished, bom=self.bom, lot=lot_finished
        )
        finished_production.move_raw_ids._action_assign()
        self.assertEqual(
            finished_production.move_raw_ids.move_line_ids.lot_id, lot_component
        )
        receipt = self._receive(self.component, lot_component)
        return {
            "lot_finished": lot_finished,
            "lot_component": lot_component,
            "component_production": component_production,
            "finished_production": finished_production,
            "receipt": receipt,
        }

    def test_tree_checks_are_found_from_the_top_lot(self) -> None:
        """Two levels of production: the top lot finds every check of its tree."""
        tree = self._build_tree()

        # One edge per check, so each one proves one term of the domain: the lot
        # itself, the production that made it, the component it consumed, and the
        # transfer the component arrived on.
        check_lot = self._create_check(lot_ids=[Command.set(tree["lot_finished"].ids)])
        check_production = self._create_check(
            production_id=tree["component_production"].id
        )
        check_component = self._create_check(
            move_id=tree["finished_production"].move_raw_ids.id,
            component_id=self.component.id,
        )
        check_receipt = self._create_check(picking_id=tree["receipt"].id)
        unrelated_check = self._create_check()

        tree_checks = self._tree_checks(tree["lot_finished"])
        for check in (check_lot, check_production, check_component, check_receipt):
            self.assertIn(check, tree_checks)
        self.assertNotIn(unrelated_check, tree_checks)
        self.assertEqual(
            tree["lot_finished"]._get_recursive_lot_ids(),
            {tree["lot_finished"].id, tree["lot_component"].id},
        )

        # What the button counts and what it opens have to agree.
        opened = self.env["quality.check"].search(
            tree["lot_finished"].action_open_recursive_quality_checks()["domain"]
        )
        self.assertEqual(opened, tree_checks)
        self.assertEqual(tree["lot_finished"].recursive_check_qty, len(tree_checks))

    def test_standard_lot_checks_are_left_alone(self) -> None:
        """The core button keeps showing this lot only, the tree button widens."""
        tree = self._build_tree()
        lot_finished = tree["lot_finished"]
        own_check = self._create_check(lot_ids=[Command.set(lot_finished.ids)])
        check_production = self._create_check(
            production_id=tree["component_production"].id
        )
        check_receipt = self._create_check(picking_id=tree["receipt"].id)

        own_checks = self._own_checks(lot_finished)
        self.assertIn(own_check, own_checks)
        self.assertNotIn(check_production, own_checks)
        self.assertNotIn(check_receipt, own_checks)
        self.assertEqual(lot_finished.quality_check_qty, len(own_checks))

        opened = self.env["quality.check"].search(
            lot_finished.action_open_quality_checks()["domain"]
        )
        self.assertEqual(opened, own_checks)

        tree_checks = self._tree_checks(lot_finished)
        self.assertGreater(len(tree_checks), len(own_checks))
        self.assertGreater(
            lot_finished.recursive_check_qty, lot_finished.quality_check_qty
        )

    def test_cycle_does_not_loop(self) -> None:
        """Two orders consuming each other's lot: the walk must still end.

        A repack registered by hand as a raw move, which is the only way this state
        comes about: two BoMs consuming each other's product are refused by the
        product cycle check.  Whatever the cause, the traversal has to stop, and it
        still has to find both lots.
        """
        lot_component = self._create_lot(self.component, "REC-CYCLE-COMPONENT")
        lot_finished = self._create_lot(self.finished, "REC-CYCLE-FINISHED")
        component_production = self._create_production(
            self.component, lot=lot_component
        )
        self.env["stock.quant"]._update_available_quantity(
            self.component,
            component_production.location_src_id,
            1.0,
            lot_id=lot_component,
        )
        finished_production = self._create_production(
            self.finished, bom=self.bom, lot=lot_finished
        )
        finished_production.move_raw_ids._action_assign()
        # The order making the component also consumes the finished lot, which
        # brings the walk back to where it started.
        repack_move = self.env["stock.move"].create(
            {
                "product_id": self.finished.id,
                "product_uom": self.finished.uom_id.id,
                "product_uom_qty": 1.0,
                "raw_material_production_id": component_production.id,
                "location_id": component_production.location_src_id.id,
                "location_dest_id": component_production.location_src_id.id,
            }
        )
        self.env["stock.move.line"].create(
            {
                "move_id": repack_move.id,
                "product_id": self.finished.id,
                "product_uom_id": self.finished.uom_id.id,
                "lot_id": lot_finished.id,
                "quantity": 1.0,
                "location_id": repack_move.location_id.id,
                "location_dest_id": repack_move.location_dest_id.id,
            }
        )

        self.assertEqual(
            lot_finished._get_recursive_lot_ids(),
            {lot_finished.id, lot_component.id},
        )

    def test_lot_without_production_keeps_its_own_checks(self) -> None:
        """A lot nobody produced reaches nothing else."""
        lot_received = self._create_lot(self.component, "REC-RECEIVED")
        other_lot = self._create_lot(self.component, "REC-UNRELATED")
        check = self._create_check(lot_ids=[Command.set(lot_received.ids)])
        other_check = self._create_check(lot_ids=[Command.set(other_lot.ids)])

        self.assertEqual(self._tree_checks(lot_received), check)
        self.assertNotIn(other_check, self._tree_checks(lot_received))
        self.assertEqual(lot_received._get_recursive_lot_ids(), {lot_received.id})

    def test_cancelled_picking_is_left_out(self) -> None:
        """A cancelled transfer moves nothing, so its check is not part of the tree."""
        lot_received = self._create_lot(self.component, "REC-CANCELLED")
        cancelled = self._receive(self.component, lot_received)
        cancelled.action_cancel()
        check = self._create_check(lot_ids=[Command.set(lot_received.ids)])
        cancelled_check = self._create_check(picking_id=cancelled.id)

        self.assertEqual(self._tree_checks(lot_received), check)
        self.assertNotIn(cancelled_check, self._tree_checks(lot_received))

    def test_empty_recordset(self) -> None:
        """No lot, no tree: the domain still builds and matches nothing."""
        lots = self.env["stock.lot"]
        self.assertEqual(lots._get_recursive_lot_ids(), set())
        self.assertFalse(
            self.env["quality.check"].search(lots._get_recursive_quality_check_domain())
        )
