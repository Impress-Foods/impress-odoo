import logging
from datetime import date

from .test_common import CampaignCase

_logger = logging.getLogger(__name__)


class TestMrpCampaignCreator(CampaignCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wizard_model = cls.env["mrp.campaign.creator"]

    def test_available_demand_move_ids(self):
        """Test that available_demand_move_ids only includes moves whose product's
        root anchor is the selected anchor product."""
        # Create a move for a product that uses bulk_material as anchor
        move_anchor = self.env["stock.move"].create(
            {
                "name": "move anchor",
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
            }
        )
        # Create a move for a product that doesn't use bulk_material as anchor
        # (Using product_no_bom which has no anchor)
        move_no_anchor = self.env["stock.move"].create(
            {
                "name": "move no anchor",
                "product_id": self.product_no_bom.id,
                "product_uom_qty": 5.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
            }
        )

        # Confirm moves to move them out of 'draft' state
        (move_anchor | move_no_anchor)._action_confirm()

        wizard = self.wizard_model.create(
            {
                "product_id": self.bulk_material.id,
            }
        )

        # available_demand_move_ids should include move_anchor but not move_no_anchor
        self.assertIn(move_anchor, wizard.available_demand_move_ids)
        self.assertNotIn(move_no_anchor, wizard.available_demand_move_ids)

    def test_available_demand_move_ids_no_product(self):
        """Test that available_demand_move_ids is empty when no product_id is set."""
        wizard = self.wizard_model.create({})
        self.assertFalse(wizard.available_demand_move_ids)

    def test_make_campaign(self):
        """Test the full campaign creation process via the wizard."""
        move_1 = self.env["stock.move"].create(
            {
                "name": "move 1",
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
            }
        )
        move_2 = self.env["stock.move"].create(
            {
                "name": "move 2",
                "product_id": self.int_prod_x_blue.id,
                "product_uom_qty": 20.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
            }
        )

        planned_date = date(2026, 3, 3)
        wizard = self.wizard_model.create(
            {
                "product_id": self.bulk_material.id,
                "planned_date": planned_date,
                "demand_move_ids": [(6, 0, [move_1.id, move_2.id])],
            }
        )

        action = wizard.make_campaign()
        campaign_id = action.get("res_id")
        campaign = self.env["mrp.campaign"].browse(campaign_id)

        self.assertTrue(campaign.exists())
        self.assertEqual(campaign.product_id, self.bulk_material)
        self.assertEqual(campaign.date_planned_start, planned_date)

        # Check demand lines
        self.assertEqual(len(campaign.demand_line_ids), 2)

        # Verify moves are correctly linked via proxies
        proxies = self.env["mrp.campaign.demand.proxy"].search(
            [("campaign_id", "=", campaign.id)]
        )
        self.assertEqual(len(proxies), 2)
        self.assertCountEqual(proxies.mapped("move_id"), move_1 | move_2)

        # Verify promised quantities
        proxy_1 = proxies.filtered(lambda p: p.move_id == move_1)
        self.assertEqual(proxy_1.promised_qty, 10.0)
        proxy_2 = proxies.filtered(lambda p: p.move_id == move_2)
        self.assertEqual(proxy_2.promised_qty, 20.0)
