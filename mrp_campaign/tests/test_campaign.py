import logging
from datetime import date, timedelta

from odoo.exceptions import UserError

from .test_common import CampaignCase

_logger = logging.getLogger(__name__)


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
        campaign.production_ids.write({"qty_producing": 10})
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
