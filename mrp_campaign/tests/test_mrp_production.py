from odoo.addons.mrp.models.mrp_production import MrpProduction

from .test_common import CampaignCase


class TestMrpProduction(CampaignCase):
    def test_split_production(self):
        campaign = self.env["mrp.campaign"].create(
            {"product_id": self.bulk_material.id}
        )
        campaign_line = self.env["mrp.campaign.line"].create(
            {"product_id": self.end_prod_a_blue.id, "campaign_id": campaign.id}
        )
        production: MrpProduction = self.env["mrp.production"].create(
            {
                "product_id": self.end_prod_a_blue.id,
                "campaign_line_id": campaign_line.id,
                "product_qty": 100.0,
            }
        )
        production.action_confirm()
        production._set_lot_producing()
        splits: MrpProduction = production._split_productions(
            amounts={production: [50.0, 50.0]}
        )
        self.assertEqual(len(splits), 2)

        self.assertEqual(splits[0].lot_producing_id, production.lot_producing_id)
        self.assertEqual(splits[0].campaign_line_id, production.campaign_line_id)
        self.assertEqual(splits[0].campaign_id, production.campaign_id)

        self.assertEqual(splits[1].lot_producing_id, production.lot_producing_id)
        self.assertEqual(splits[1].campaign_line_id, production.campaign_line_id)
        self.assertEqual(splits[1].campaign_id, production.campaign_id)
