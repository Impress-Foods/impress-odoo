import json

from odoo import fields

from .test_common import CampaignDirectCase


class TestMrpCampaignWizard(CampaignDirectCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wizard_model = cls.env["mrp.campaign.wizard.creator"].with_context(
            default_workflow_type="direct"
        )

    def test_wizard_create_with_product(self):
        """Test wizard creation with a product sets available_lines."""
        wizard = self.wizard_model.create(
            {
                "product_id": self.bulk_material.id,
            }
        )
        self.assertEqual(wizard.product_id.id, self.bulk_material.id)
        wizard._onchange_product_id()
        self.assertTrue(wizard.available_lines)
        available = json.loads(wizard.available_lines)
        self.assertIsInstance(available, list)

    def test_wizard_create_without_product(self):
        """Test wizard creation without product has empty available_lines."""
        wizard = self.wizard_model.create({})
        self.assertFalse(wizard.product_id)
        self.assertIn(wizard.available_lines, (False, None, "[]", ""))

    def test_get_available_lines_returns_stock_moves(self):
        """Test _get_available_lines returns stock moves with correct JSON format."""
        picking = self.env["stock.picking"].create(
            {"picking_type_id": self.env.ref("stock.picking_type_out").id}
        )
        move = self.env["stock.move"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "picking_id": picking.id,
            }
        )
        move._action_confirm()

        wizard = self.wizard_model.create(
            {
                "product_id": self.bulk_material.id,
            }
        )
        wizard._onchange_product_id()

        available = json.loads(wizard.available_lines)
        self.assertGreaterEqual(len(available), 1)

        move_data = next((m for m in available if m["id"] == move.id), None)
        self.assertIsNotNone(move_data)
        self.assertIn("name", move_data)
        self.assertIn("qty", move_data)
        self.assertIn("date", move_data)
        self.assertIn("additional_ref", move_data)

    def test_get_available_lines_filters_by_anchor(self):
        """Test _get_available_lines only includes moves with correct anchor product."""

        picking = self.env["stock.picking"].create(
            {"picking_type_id": self.env.ref("stock.picking_type_out").id}
        )

        move_anchor = self.env["stock.move"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "picking_id": picking.id,
            }
        )
        move_no_anchor = self.env["stock.move"].create(
            {
                "product_id": self.product_no_bom.id,
                "product_uom_qty": 5.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "picking_id": picking.id,
            }
        )

        (move_anchor | move_no_anchor)._action_confirm()

        wizard = self.wizard_model.create(
            {
                "product_id": self.bulk_material.id,
            }
        )
        wizard._onchange_product_id()

        available = json.loads(wizard.available_lines)
        available_ids = [m["id"] for m in available]
        self.assertIn(move_anchor.id, available_ids)
        self.assertNotIn(move_no_anchor.id, available_ids)

    def test_get_selected_sources(self):
        """Test _get_selected_sources returns moves based on selected_line_ids."""
        picking = self.env["stock.picking"].create(
            {"picking_type_id": self.env.ref("stock.picking_type_out").id}
        )
        move = self.env["stock.move"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "picking_id": picking.id,
            }
        )
        move._action_confirm()

        wizard = self.wizard_model.create(
            {
                "product_id": self.bulk_material.id,
            }
        )
        wizard._onchange_product_id()
        wizard.selected_line_ids = json.dumps([move.id])

        selected = wizard._get_selected_sources()
        self.assertIn(move, selected)

    def test_get_selected_sources_empty(self):
        """Test _get_selected_sources returns empty recordset when no selection."""
        wizard = self.wizard_model.create(
            {
                "product_id": self.bulk_material.id,
            }
        )
        wizard._onchange_product_id()

        selected = wizard._get_selected_sources()
        self.assertFalse(selected)

    def test_process_wizard_creates_campaign_and_demands(self):
        """Test process_wizard creates campaign with demands from selected moves."""
        picking = self.env["stock.picking"].create(
            {"picking_type_id": self.env.ref("stock.picking_type_out").id}
        )
        move = self.env["stock.move"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "picking_id": picking.id,
            }
        )
        move._action_confirm()

        wizard = self.wizard_model.create(
            {
                "product_id": self.bulk_material.id,
                "planned_date": fields.Date.today(),
            }
        )
        wizard._onchange_product_id()
        wizard.selected_line_ids = json.dumps([move.id])

        action = wizard.process_wizard()
        self.assertTrue(action)
        self.assertEqual(action["res_model"], "mrp.campaign")

        campaign = self.env["mrp.campaign"].browse(action["res_id"])
        self.assertTrue(campaign.exists())
        self.assertEqual(campaign.product_id, self.bulk_material)
        self.assertEqual(campaign.workflow_type, "direct")

        targets = self.env["mrp.campaign.demand.target"].search(
            [("campaign_id", "=", campaign.id)]
        )
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets.target_id, move.id)

    def test_process_wizard_adds_to_existing_campaign(self):
        """Test process_wizard adds demands to existing campaign."""
        existing_campaign = self.create_campaign(self.bulk_material)
        picking = self.env["stock.picking"].create(
            {"picking_type_id": self.env.ref("stock.picking_type_out").id}
        )
        move = self.env["stock.move"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "picking_id": picking.id,
            }
        )
        move._action_confirm()

        wizard = self.wizard_model.create(
            {
                "campaign_id": existing_campaign.id,
                "product_id": self.bulk_material.id,
            }
        )
        wizard._onchange_product_id()
        wizard.selected_line_ids = json.dumps([move.id])

        action = wizard.process_wizard()
        self.assertIsNone(action)

        targets = self.env["mrp.campaign.demand.target"].search(
            [("campaign_id", "=", existing_campaign.id)]
        )
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets.target_id, move.id)

    def test_process_wizard_reuses_existing_demand_for_same_product(self):
        """Test reuse existing demand when adding target for same product."""
        existing_campaign = self.create_campaign(self.bulk_material)
        existing_campaign.workflow_type = "direct"

        existing_demand = self.env["mrp.campaign.demand"].create(
            {
                "campaign_id": existing_campaign.id,
                "product_id": self.int_prod_x_red.id,
            }
        )

        picking_1 = self.env["stock.picking"].create(
            {"picking_type_id": self.env.ref("stock.picking_type_out").id}
        )
        move_1 = self.env["stock.move"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 5.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "picking_id": picking_1.id,
            }
        )
        move_1._action_confirm()

        self.env["mrp.campaign.demand.target"].create(
            {
                "demand_id": existing_demand.id,
                "workflow_type": "direct",
                "target_id": move_1.id,
                "promised_qty": 5.0,
            }
        )

        picking_2 = self.env["stock.picking"].create(
            {"picking_type_id": self.env.ref("stock.picking_type_out").id}
        )
        move_2 = self.env["stock.move"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "picking_id": picking_2.id,
            }
        )
        move_2._action_confirm()

        wizard = self.wizard_model.create(
            {
                "campaign_id": existing_campaign.id,
                "product_id": self.bulk_material.id,
            }
        )
        wizard._onchange_product_id()
        wizard.selected_line_ids = json.dumps([move_2.id])

        wizard.process_wizard()

        demands = self.env["mrp.campaign.demand"].search(
            [("campaign_id", "=", existing_campaign.id)]
        )
        self.assertEqual(
            len(demands), 1, "Should reuse existing demand, not create new one"
        )

        targets = self.env["mrp.campaign.demand.target"].search(
            [("campaign_id", "=", existing_campaign.id), ("target_id", "=", move_2.id)]
        )
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets.demand_id, existing_demand)

    def test_process_wizard_no_selection(self):
        """Test process_wizard w no selec. still creates campaign w product select."""
        wizard = self.wizard_model.create(
            {
                "product_id": self.bulk_material.id,
                "planned_date": fields.Date.today(),
            }
        )
        wizard._onchange_product_id()

        action = wizard.process_wizard()
        self.assertTrue(action)

        campaign = self.env["mrp.campaign"].search(
            [("product_id", "=", self.bulk_material.id)]
        )
        self.assertTrue(campaign)

    def test_product_id_change_resets_selection(self):
        """Test that changing product_id clears the selection."""

        picking = self.env["stock.picking"].create(
            {"picking_type_id": self.env.ref("stock.picking_type_out").id}
        )
        move = self.env["stock.move"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "picking_id": picking.id,
            }
        )
        move._action_confirm()

        wizard = self.wizard_model.create(
            {
                "product_id": self.bulk_material.id,
            }
        )
        wizard._onchange_product_id()
        wizard.selected_line_ids = json.dumps([move.id])
        self.assertEqual(wizard._get_selected_sources(), move)

        wizard.product_id = self.int_prod_x_red.id
        wizard._onchange_product_id()
        self.assertEqual(wizard.selected_line_ids, "[]")
        self.assertFalse(wizard._get_selected_sources())

    def test_default_get_prefills_from_context(self):
        """Test default_get pre-fills campaign and product from context."""
        campaign = self.create_campaign(self.bulk_material)

        wizard = self.wizard_model.with_context(default_campaign_id=campaign.id).create(
            {}
        )

        self.assertEqual(wizard.campaign_id, campaign)
        self.assertEqual(wizard.product_id, self.bulk_material)

    def test_default_get_no_context_no_prefill(self):
        """Test default_get does not prefill when no campaign in context."""
        wizard = self.wizard_model.create({})

        self.assertFalse(wizard.campaign_id)
        self.assertFalse(wizard.product_id)

    def test_default_get_populates_available_lines(self):
        """Test default_get pop. available_lines when campaign has workflow_type."""
        existing_campaign = self.create_campaign(self.bulk_material)
        existing_campaign.workflow_type = "direct"

        # Create two outgoing moves for the same product
        picking_1 = self.env["stock.picking"].create(
            {"picking_type_id": self.env.ref("stock.picking_type_out").id}
        )
        move1 = self.env["stock.move"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 5.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "picking_id": picking_1.id,
            }
        )
        picking_2 = self.env["stock.picking"].create(
            {"picking_type_id": self.env.ref("stock.picking_type_out").id}
        )
        move2 = self.env["stock.move"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "picking_id": picking_2.id,
            }
        )

        (move1 | move2)._action_confirm()
        self.assertEqual(len(picking_1.move_ids), 1)
        self.assertEqual(len(picking_2.move_ids), 1)

        # Add move1 to campaign (fully allocated)
        demand = self.env["mrp.campaign.demand"].create(
            {
                "campaign_id": existing_campaign.id,
                "product_id": self.int_prod_x_red.id,
            }
        )
        self.env["mrp.campaign.demand.target"].create(
            {
                "demand_id": demand.id,
                "workflow_type": "direct",
                "target_id": move1.id,
                "promised_qty": 5.0,
            }
        )

        # Open wizard with campaign_id (simulating UI)
        wizard = self.wizard_model.with_context(
            default_campaign_id=existing_campaign.id
        ).create({})

        # Check that workflow_type and product_id are set
        self.assertEqual(wizard.workflow_type, "direct")
        self.assertEqual(wizard.product_id, self.bulk_material)
        # Check that available_lines is populated (should contain both moves)
        self.assertTrue(wizard.available_lines)
        available = json.loads(wizard.available_lines)
        available_ids = [item["id"] for item in available]

        self.assertIn(move2.id, available_ids)
        self.assertNotIn(move1.id, available_ids)

        # Find qty for each move
        for item in available:
            if item["id"] == move2.id:
                self.assertEqual(item["qty"], 10.0)
