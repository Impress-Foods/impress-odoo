from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError

from .test_common import CampaignCase


class TestCampaign(CampaignCase):
    def test_sync_dates_valid(self) -> None:
        DATE = date(year=2025, month=3, day=14)
        NEW_DATE = DATE + timedelta(days=2)

        campaign = self.create_campaign(self.bulk_material)
        campaign.date_planned_start = DATE
        self.create_demand(self.end_prod_a_red, 100, campaign)

        campaign.action_plan()
        campaign.action_confirm()

        # Check if all MOs have to correct date to start with
        self.assertTrue(
            all([mo.date_start.date() == DATE for mo in campaign.production_ids])
        )

        campaign.date_planned_start = NEW_DATE
        self.assertTrue(
            all([mo.date_start.date() == NEW_DATE for mo in campaign.production_ids])
        )

    def test_sync_dates_valid_done_mo(self) -> None:
        DATE = date(year=2025, month=3, day=14)
        NEW_DATE = DATE + timedelta(days=2)

        campaign = self.create_campaign(self.bulk_material)
        campaign.date_planned_start = DATE
        self.create_demand(self.end_prod_a_red, 100, campaign)

        campaign.action_plan()
        campaign.action_confirm()

        mo_1 = campaign.production_ids[0]
        mo_1.write({"state": "done"})

        # Check if all MOs have to correct date to start with
        self.assertTrue(
            all([mo.date_start.date() == DATE for mo in campaign.production_ids])
        )

        campaign.date_planned_start = NEW_DATE
        self.assertTrue(
            all(
                [
                    mo.date_start.date() == NEW_DATE
                    for mo in (campaign.production_ids - mo_1)
                ]
            )
        )
        self.assertTrue(mo_1.date_start.date() == DATE)

    def test_unlink_campaign_draft(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        self.assertEqual(campaign.state, "draft")
        campaign.unlink()

    def test_unlink_campaign_planned(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.bulk_material, 100, campaign)
        campaign.action_plan()
        self.assertEqual(campaign.state, "plan")
        campaign.unlink()

    def test_unlink_campaign_confirmed(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.bulk_material, 100, campaign)
        campaign.action_plan()
        campaign.action_confirm()
        self.assertEqual(campaign.state, "confirm")
        campaign.unlink()

    def test_unlink_campaign_progress(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.bulk_material, 100, campaign)
        campaign.action_plan()
        campaign.action_confirm()
        campaign.production_ids.qty_producing = 10
        self.assertEqual(campaign.state, "progress")
        message = "Can't delete a campaign in progress!"
        with self.assertRaisesRegex(UserError, message):
            campaign.unlink()

    def test_unlink_campaign_done(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.bulk_material, 100, campaign)
        campaign.action_plan()
        campaign.action_confirm()
        campaign.production_ids.button_mark_done()
        self.assertEqual(campaign.state, "done")
        message = "Can't delete a completed campaign!"
        with self.assertRaisesRegex(UserError, message):
            campaign.unlink()

    def test_unlink_campaign_cancelled(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.bulk_material, 100, campaign)
        campaign.action_plan()
        campaign.action_confirm()
        campaign.production_ids.action_cancel()
        self.assertEqual(campaign.state, "cancel")
        campaign.unlink()

    def test_sync_lots_on_productions(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.end_prod_a_red, 100, campaign)
        campaign.action_plan()
        campaign.action_confirm()

        source_mo = campaign.production_ids[0]
        source_mo._set_lot_producing()
        seed_lot = source_mo.lot_producing_id
        lot_name = seed_lot.name
        self.assertEqual(campaign.lot_name, lot_name)
        self.assertTrue(
            all(
                [
                    lot.name == lot_name
                    for lot in campaign.production_ids.mapped("lot_producing_id")
                ]
            )
        )

    def test_sync_lot_from_campaign(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.end_prod_a_red, 100, campaign)
        campaign.action_plan()
        campaign.action_confirm()

        lot_name = "CAMPAIGN-LOT-123"
        campaign.write({"lot_name": lot_name})

        self.assertTrue(
            all(
                [
                    lot.name == lot_name
                    for lot in campaign.production_ids.mapped("lot_producing_id")
                ]
            )
        )

    def test_sync_lot_with_done_mo(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.end_prod_a_red, 100, campaign)
        campaign.action_plan()
        campaign.action_confirm()

        # Mark one MO as done with a specific lot
        mo_done = campaign.production_ids[0]
        mo_done._set_lot_producing()
        initial_lot_name = mo_done.lot_producing_id.name
        mo_done.button_mark_done()
        self.assertEqual(mo_done.state, "done")

        # Try to change the campaign lot name
        new_lot_name = "NEW-CAMPAIGN-LOT"
        # This should ideally not crash and should skip the done MO
        campaign.write({"lot_name": new_lot_name})

        self.assertEqual(mo_done.lot_producing_id.name, initial_lot_name)
        self.assertTrue(
            all(
                [
                    mo.lot_producing_id.name == new_lot_name
                    for mo in (campaign.production_ids - mo_done)
                ]
            )
        )

    def test_action_reset(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.bulk_material, 100, campaign)
        self.assertGreaterEqual(len(campaign.demand_line_ids), 1)
        campaign.action_plan()
        self.assertGreater(len(campaign.line_ids), 0)
        self.assertGreater(len(campaign.production_ids), 0)

        self.assertEqual(campaign.state, "plan")
        self.assertTrue(campaign.line_ids)
        self.assertTrue(campaign.production_ids)

        campaign.action_reset()
        self.assertEqual(campaign.state, "draft")
        self.assertFalse(campaign.line_ids)
        self.assertFalse(campaign.production_ids)

    def test_split_single_demand(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        campaign.date_planned_start = fields.Date.today()
        demand = self.create_demand(self.end_prod_a_red, 100.0, campaign)
        campaign.action_plan()

        original_production_count = len(campaign.production_ids)
        target_id = demand.target_ids[0].id

        bo_campaign = campaign._split({target_id: 60.0})

        self.assertEqual(demand.target_qty, 60.0)
        self.assertTrue(bo_campaign)
        self.assertEqual(bo_campaign.bo_source_id, campaign)
        self.assertEqual(len(bo_campaign.demand_line_ids), 1)
        self.assertEqual(bo_campaign.demand_line_ids.target_qty, 40.0)

        updated_line = campaign.line_ids.filtered(
            lambda line: line.product_id == self.end_prod_a_red
        )
        self.assertEqual(updated_line.qty, 60.0)
        self.assertEqual(len(campaign.production_ids), original_production_count)

    def test_split_multiple_demands(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        campaign.date_planned_start = fields.Date.today()
        demand1 = self.create_demand(self.end_prod_a_red, 100.0, campaign)
        demand2 = self.create_demand(self.end_prod_a_blue, 50.0, campaign)
        demand3 = self.create_demand(self.end_prod_a_blue, 200.0, campaign)

        campaign.action_plan()

        bo_campaign = campaign._split(
            {
                demand1.target_ids[0].id: 80.0,
                demand2.target_ids[0].id: 30.0,
                demand3.target_ids[0].id: 200.0,
            }
        )

        self.assertEqual(demand1.target_qty, 80.0)
        self.assertEqual(demand2.target_qty, 30.0)
        self.assertEqual(demand3.target_qty, 200.0)
        self.assertEqual(len(campaign.demand_line_ids), 3)
        self.assertEqual(len(bo_campaign.demand_line_ids), 2)
        bo_demand_by_product = {d.product_id: d for d in bo_campaign.demand_line_ids}
        self.assertEqual(bo_demand_by_product[self.end_prod_a_red].target_qty, 20.0)
        self.assertEqual(bo_demand_by_product[self.end_prod_a_blue].target_qty, 20.0)

    def test_split_no_backorder_qty_returns_empty_recordset(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        campaign.date_planned_start = fields.Date.today()
        demand = self.create_demand(self.end_prod_a_red, 100.0, campaign)
        campaign.action_plan()

        original_line_qty = campaign.line_ids.filtered(
            lambda line: line.product_id == self.end_prod_a_red
        ).qty
        target_id = demand.target_ids[0].id

        bo_campaign = campaign._split({target_id: 100.0})

        self.assertFalse(bo_campaign)
        self.assertEqual(len(bo_campaign), 0)
        self.assertEqual(demand.target_qty, 100.0)

        updated_line = campaign.line_ids.filtered(
            lambda line: line.product_id == self.end_prod_a_red
        )
        self.assertEqual(updated_line.qty, original_line_qty)

    def test_split_empty_dict_returns_empty_recordset(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        campaign.date_planned_start = fields.Date.today()
        demand = self.create_demand(self.end_prod_a_red, 100.0, campaign)
        campaign.action_plan()

        bo_campaign = campaign._split({})

        self.assertFalse(bo_campaign)
        self.assertEqual(len(bo_campaign), 0)
        self.assertEqual(demand.target_ids[0].promised_qty, 100.0)

    def test_split_demand_not_in_campaign_raises(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        campaign.date_planned_start = fields.Date.today()
        other_campaign = self.create_campaign(self.bulk_material)
        other_demand = self.create_demand(self.end_prod_a_red, 50.0, other_campaign)

        with self.assertRaisesRegex(ValidationError, "do not belong to this campaign"):
            campaign._split({other_demand.target_ids[0].id: 25.0})

    def test_split_creates_lines_in_backorder(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        campaign.date_planned_start = fields.Date.today()
        demand = self.create_demand(self.end_prod_a_red, 100.0, campaign)
        campaign.action_plan()
        target_id = demand.target_ids[0].id

        bo_campaign = campaign._split({target_id: 50.0})

        self.assertEqual(bo_campaign.demand_line_ids[0].bom_id, demand.bom_id)

        self.assertTrue(bo_campaign.line_ids)
        self.assertTrue(bo_campaign.production_ids)

    def test_split_full_demand_to_backorder(self) -> None:
        QTY = 100.0
        campaign = self.create_campaign(self.bulk_material)
        campaign.date_planned_start = fields.Date.today()
        demand = self.create_demand(self.end_prod_a_red, QTY, campaign)
        campaign.action_plan()
        target = demand.target_ids[0]

        bo_campaign = campaign._split({target.id: 0})

        self.assertTrue(bo_campaign)
        self.assertEqual(len(bo_campaign.demand_line_ids), 1)
        self.assertEqual(bo_campaign.demand_line_ids.target_qty, QTY)
        self.assertEqual(demand.campaign_id.id, bo_campaign.id)

        self.assertFalse(
            campaign.line_ids.filtered(
                lambda line: line.product_id == self.end_prod_a_red
            )
        )
