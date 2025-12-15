# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

try:
    import psycopg2
except ImportError:
    psycopg2 = None


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
        self.finished_product.route_ids = [(6, 0, [manufacture_route.id])]
        self.intermediate_product.route_ids = [(6, 0, [manufacture_route.id])]

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
        with self.assertRaises((UserError, psycopg2.errors.ForeignKeyViolation)):
            campaign.unlink()
