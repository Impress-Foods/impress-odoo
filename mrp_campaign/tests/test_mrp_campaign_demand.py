import logging

from ..models.mrp_campaign import MrpCampaign
from .test_common import CampaignCase

_logger = logging.getLogger(__name__)


class TestMrpCampaignDemand(CampaignCase):
    def test_get_get_anchor_factor(self) -> None:
        FACTOR = 2.0 * 3.0  # 2/1 end -> int, 3/1 int -> bulk
        campaign: MrpCampaign = self.create_campaign(self.bulk_material)

        demand_line = self.create_demand(self.end_prod_a_blue, 100, campaign)
        campaign._construct_tree_from_demand()

        value = demand_line._get_anchor_factor()
        self.assertEqual(value, FACTOR)

    def test_create_campaign_line_single(self) -> None:
        QTY = 100.0
        campaign: MrpCampaign = self.create_campaign(self.bulk_material)
        demand_line = self.create_demand(self.end_prod_a_blue, QTY, campaign)

        campaign_line = demand_line.create_campaign_line()
        self.assertEqual(len(campaign_line), 1)
        self.assertEqual(len(campaign.line_ids), 1)
        self.assertEqual(campaign_line.product_id, self.end_prod_a_blue)
        self.assertEqual(campaign_line.qty, QTY)
        self.assertEqual(campaign_line.bom_id, self.bom_end_prod_a)
        self.assertEqual(campaign_line.campaign_id, campaign)

    def test_create_campaign_line_multiple(self) -> None:
        QTY = 100.0
        campaign: MrpCampaign = self.create_campaign(self.bulk_material)
        demand_line_1 = self.create_demand(self.end_prod_a_blue, QTY, campaign)
        demand_line_2 = self.create_demand(self.end_prod_a_red, QTY, campaign)

        campaign_line = (demand_line_1 + demand_line_2).create_campaign_line()
        self.assertEqual(len(campaign_line), 2)
        self.assertEqual(len(campaign.line_ids), 2)

    def test_create_campaign_line_existing(self) -> None:
        QTY = 100
        campaign: MrpCampaign = self.create_campaign(self.bulk_material)
        demand_line_1 = self.create_demand(self.end_prod_a_blue, QTY, campaign)
        demand_line_2 = self.create_demand(self.end_prod_a_blue, QTY, campaign)

        campaign_line_1 = demand_line_1.create_campaign_line()
        campaign_line_2 = demand_line_2.create_campaign_line()

        self.assertEqual(campaign_line_1.id, campaign_line_2.id)
        self.assertEqual(campaign_line_1.qty, 2 * QTY)
        self.assertEqual(len(campaign.line_ids), 1)
