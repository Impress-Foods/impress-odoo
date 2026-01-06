# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from psycopg2.errors import ForeignKeyViolation

from odoo import fields
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


class TestMrpCampaign(TransactionCase):
    def setUp(self):
        super().setUp()
        self.MrpProduction = self.env["mrp.production"]
        self.MrpCampaign = self.env["mrp.campaign"]
        self.StockMove = self.env["stock.move"]
        # Main product that will be consumed
        self.finished_product = self.env["product.product"].create(
            {"name": "Finished Product", "type": "product"}
        )
        # Intermediate product that will be managed by campaigns
        self.intermediate_product = self.env["product.product"].create(
            {
                "name": "Campaign Managed Item",
                "type": "product",
                "is_campaign_manufactured": True,
                "mrp_max_batch_size": 100,
                "campaign_bucket_size": 1,
                "campaign_bucket_type": "day",
            }
        )
        # Create BoMs
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": self.intermediate_product.product_tmpl_id.id,
                "product_qty": 1,
            }
        )
        self.main_bom = self.env["mrp.bom"].create(
            {
                "product_tmpl_id": self.finished_product.product_tmpl_id.id,
                "product_qty": 1,
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.intermediate_product.id,
                            "product_qty": 2,
                        },
                    )
                ],
            }
        )
        # Set up routes
        manufacture_route = self.env.ref("mrp.route_warehouse0_manufacture")
        mto_route = self.env.ref("stock.route_warehouse0_mto")
        mto_route.active = True

        self.finished_product.route_ids = [(6, 0, [manufacture_route.id])]
        self.intermediate_product.route_ids = [
            (6, 0, [manufacture_route.id, mto_route.id])
        ]

    def test_01_procurement_creates_campaign(self):
        """Triggering a procurement for a campaign-managed product should
        create a draft campaign and collect the demand move."""

        # Create a Production Order for the main product and confirm it.
        # This will trigger the procurement chain for its components.
        mo = self.MrpProduction.create(
            {
                "product_id": self.finished_product.id,
                "product_uom_id": self.finished_product.uom_id.id,
                "product_qty": 10,
                "bom_id": self.main_bom.id,
            }
        )
        mo.action_confirm()

        # Find the move for the intermediate product that was created
        demand_move = self.StockMove.search(
            [
                ("raw_material_production_id", "=", mo.id),
                ("product_id", "=", self.intermediate_product.id),
            ]
        )
        self.assertTrue(demand_move, "Demand move for intermediate was not created.")

        # Check that a campaign was created for the intermediate product
        campaign = self.MrpCampaign.search(
            [("product_id", "=", self.intermediate_product.id)]
        )
        self.assertEqual(len(campaign), 1, "A campaign should have been created.")
        self.assertEqual(campaign.state, "draft", "New campaign should be in draft.")

        # Check that the move was collected and demand is correct
        self.assertIn(
            demand_move,
            campaign.demand_move_ids,
            "The demand move was not added to the campaign.",
        )
        self.assertEqual(
            campaign.total_demand_qty, 20, "Total demand should be 20 (10 * 2)."
        )

    def test_02_confirm_campaign_creates_mos(self):
        """Confirming a campaign should create batched provider MOs."""
        # Setup: Create a campaign with demand
        self.test_01_procurement_creates_campaign()
        campaign = self.MrpCampaign.search(
            [("product_id", "=", self.intermediate_product.id)]
        )

        # Confirm the campaign
        campaign.action_confirm()

        self.assertEqual(campaign.state, "confirmed", "Campaign should be 'confirmed'.")
        self.assertTrue(campaign.provider_mo_ids, "Provider MOs should be created.")

        # Demand was 20, batch size is 100. One MO of 20 should be created.
        self.assertEqual(len(campaign.provider_mo_ids), 1)
        self.assertEqual(campaign.provider_mo_ids.product_qty, 20)

    def test_03_cancel_campaign_preserves_mos(self):
        """Cancelling a campaign should only change its state, not the MOs."""
        self.test_02_confirm_campaign_creates_mos()
        campaign = self.MrpCampaign.search(
            [("product_id", "=", self.intermediate_product.id)]
        )
        provider_mos = campaign.provider_mo_ids

        # Cancel the campaign
        campaign.action_cancel()

        self.assertEqual(campaign.state, "cancel", "Campaign should be 'cancel'.")
        self.assertTrue(
            all(mo.state != "cancel" for mo in provider_mos),
            "Provider MOs should not have been cancelled.",
        )
        self.assertTrue(
            all(mo.campaign_id == campaign for mo in provider_mos),
            "Provider MOs should still be linked to the campaign.",
        )

    def test_04_delete_campaign_with_mos_raises_error(self):
        """Deleting a campaign with linked MOs should be restricted."""
        self.test_03_cancel_campaign_preserves_mos()
        campaign = self.MrpCampaign.search(
            [("product_id", "=", self.intermediate_product.id)]
        )
        self.assertTrue(
            campaign.provider_mo_ids, "Test setup failed: No provider MOs found."
        )

        # Expect an IntegrityError due to the 'ondelete=restrict' constraint
        with self.assertRaises(ForeignKeyViolation):
            campaign.unlink()

    def _create_mo_and_get_campaign(self, product, quantity=10):
        """Helper to create an MO and return the resulting campaign."""
        # Get existing demand moves for this product before creating the MO
        initial_demand_moves = self.StockMove.search(
            [
                ("product_id", "=", product.id),
                ("raw_material_production_id", "!=", False),
            ]
        )

        mo = self.MrpProduction.create(
            {
                "product_id": self.finished_product.id,
                "product_uom_id": self.finished_product.uom_id.id,
                "product_qty": quantity,
                "bom_id": self.main_bom.id,
            }
        )
        mo.action_confirm()

        # Find the new demand move created by this MO
        new_demand_move = (
            self.StockMove.search(
                [
                    ("product_id", "=", product.id),
                    ("raw_material_production_id", "=", mo.id),
                ]
            )
            - initial_demand_moves
        )

        self.assertTrue(
            new_demand_move, "Demand move for intermediate was not created."
        )
        self.assertTrue(
            new_demand_move.demanded_by_campaign_id,
            "Demand move should be linked to a campaign.",
        )

        return new_demand_move.demanded_by_campaign_id

    def test_05_procurement_creates_campaign_with_daily_bucket(self):
        """Test that a procurement for a daily-bucketed product creates a campaign for today."""
        self.intermediate_product.write(
            {"campaign_bucket_type": "day", "campaign_bucket_size": 1}
        )
        today = fields.Date.today()
        campaign = self._create_mo_and_get_campaign(self.intermediate_product)

        self.assertEqual(
            campaign.date_start, today, "Daily bucket campaign should start today."
        )
        self.assertEqual(
            campaign.date_end, today, "Daily bucket campaign should end today."
        )

    def test_06_procurement_creates_campaign_with_weekly_bucket(self):
        """Test that a procurement for a weekly-bucketed product creates a campaign for the current week."""
        self.intermediate_product.write(
            {"campaign_bucket_type": "week", "campaign_bucket_size": 1}
        )
        today = fields.Date.today()
        # Monday is 0, Sunday is 6
        expected_start_date = today - relativedelta(days=today.weekday())
        expected_end_date = (
            expected_start_date + relativedelta(weeks=1) - relativedelta(days=1)
        )

        campaign = self._create_mo_and_get_campaign(self.intermediate_product)

        self.assertEqual(
            campaign.date_start,
            expected_start_date,
            "Weekly bucket campaign should start at beginning of week.",
        )
        self.assertEqual(
            campaign.date_end,
            expected_end_date,
            "Weekly bucket campaign should end at end of week.",
        )

    def test_07_procurement_creates_campaign_with_monthly_bucket(self):
        """Test that a procurement for a monthly-bucketed product creates a campaign for the current month."""
        self.intermediate_product.write(
            {"campaign_bucket_type": "month", "campaign_bucket_size": 1}
        )
        today = fields.Date.today()
        expected_start_date = today.replace(day=1)
        expected_end_date = (
            expected_start_date + relativedelta(months=1) - relativedelta(days=1)
        )

        campaign = self._create_mo_and_get_campaign(self.intermediate_product)

        self.assertEqual(
            campaign.date_start,
            expected_start_date,
            "Monthly bucket campaign should start at beginning of month.",
        )
        self.assertEqual(
            campaign.date_end,
            expected_end_date,
            "Monthly bucket campaign should end at end of month.",
        )

    def test_08_multiple_procurements_in_same_weekly_bucket(self):
        """Test that multiple procurements within the same weekly bucket use the same campaign."""
        self.intermediate_product.write(
            {"campaign_bucket_type": "week", "campaign_bucket_size": 1}
        )
        # Create first MO
        campaign1 = self._create_mo_and_get_campaign(self.intermediate_product)
        initial_demand_moves_count = len(campaign1.demand_move_ids)

        # Simulate a different day within the same week
        # Use a day within the same week as fields.Date.today()
        today = fields.Date.today()
        day_in_same_week = (
            today + relativedelta(days=1)
            if today.weekday() < 6
            else today - relativedelta(days=1)
        )
        if (
            day_in_same_week.weekday() == today.weekday()
        ):  # ensure it's a different day, but same week
            day_in_same_week = (
                today + relativedelta(days=2)
                if today.weekday() < 5
                else today - relativedelta(days=2)
            )

        with patch("odoo.fields.Date.today", return_value=day_in_same_week):
            # Create second MO
            campaign2 = self._create_mo_and_get_campaign(self.intermediate_product)

            # Assert only one campaign exists and it's the same one
            self.assertEqual(
                campaign1,
                campaign2,
                "Procurements in same week should use the same campaign.",
            )
            self.assertEqual(
                len(campaign1.demand_move_ids),
                initial_demand_moves_count + 1,
                "Second demand move should be added to the existing campaign.",
            )

    def test_09_multiple_procurements_in_different_weekly_buckets(self):
        """Test that multiple procurements in different weekly buckets create separate campaigns."""
        self.intermediate_product.write(
            {"campaign_bucket_type": "week", "campaign_bucket_size": 1}
        )
        # Create first MO
        campaign1 = self._create_mo_and_get_campaign(self.intermediate_product)

        # Simulate a day in the next week
        today = fields.Date.today()
        day_in_next_week = today + relativedelta(weeks=1)

        with patch("odoo.fields.Date.today", return_value=day_in_next_week):
            # Create second MO
            campaign2 = self._create_mo_and_get_campaign(self.intermediate_product)

            # Assert two different campaigns are created
            self.assertNotEqual(
                campaign1,
                campaign2,
                "Procurements in different weeks should create different campaigns.",
            )

            # Verify the dates of the second campaign
            expected_start_date_c2 = day_in_next_week - relativedelta(
                days=day_in_next_week.weekday()
            )
            expected_end_date_c2 = (
                expected_start_date_c2 + relativedelta(weeks=1) - relativedelta(days=1)
            )

            self.assertEqual(campaign2.date_start, expected_start_date_c2)
            self.assertEqual(campaign2.date_end, expected_end_date_c2)
