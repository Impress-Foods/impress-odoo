import json

from odoo import fields

from .test_common import CampaignDirectCase


class TestMrpCampaignDirectWizard(CampaignDirectCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wizard_model = cls.env["mrp.campaign.direct.wizard"]

    def test_wizard_create_with_product(self):
        """Test wizard creation with a product sets available_lines."""
        wizard = self.wizard_model.create(
            {
                "product_id": self.bulk_material.id,
            }
        )
        self.assertTrue(wizard.product_id)
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
        move = self.env["stock.move"].create(
            {
                "name": "Test Move",
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
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
        self.assertTrue(len(available) >= 1)

        move_data = next((m for m in available if m["id"] == move.id), None)
        self.assertIsNotNone(move_data)
        self.assertIn("name", move_data)
        self.assertIn("qty", move_data)
        self.assertIn("date", move_data)
        self.assertIn("additional_ref", move_data)

    def test_get_available_lines_filters_by_anchor(self):
        """Test _get_available_lines only includes moves with correct anchor product."""
        move_anchor = self.env["stock.move"].create(
            {
                "name": "move anchor",
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
            }
        )
        move_no_anchor = self.env["stock.move"].create(
            {
                "name": "move no anchor",
                "product_id": self.product_no_bom.id,
                "product_uom_qty": 5.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
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
        move = self.env["stock.move"].create(
            {
                "name": "Test Move",
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
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
        move = self.env["stock.move"].create(
            {
                "name": "Test Move",
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
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

        proxies = self.env["mrp.campaign.demand.proxy"].search(
            [("campaign_id", "=", campaign.id)]
        )
        self.assertEqual(len(proxies), 1)
        self.assertEqual(proxies.move_id, move)

    def test_process_wizard_adds_to_existing_campaign(self):
        """Test process_wizard adds demands to existing campaign."""
        existing_campaign = self.create_campaign(self.bulk_material)

        move = self.env["stock.move"].create(
            {
                "name": "Test Move",
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
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

        proxies = self.env["mrp.campaign.demand.proxy"].search(
            [("campaign_id", "=", existing_campaign.id)]
        )
        self.assertEqual(len(proxies), 1)
        self.assertEqual(proxies.move_id, move)

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
        move = self.env["stock.move"].create(
            {
                "name": "Test Move",
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
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
