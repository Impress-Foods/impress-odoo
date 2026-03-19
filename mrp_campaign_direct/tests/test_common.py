from odoo.addons.mrp_campaign.tests.test_common import CampaignCase


class CampaignDirectCase(CampaignCase):
    @classmethod
    def create_full_campaign(cls, product, qty):
        """Creates campaign, demand, move, and proxy for testing."""
        campaign = cls.create_campaign(cls.bulk_material)
        demand = cls.create_demand(product, qty, campaign)
        move = cls.env["stock.move"].create(
            {
                "name": f"test move for {product.display_name}",
                "product_id": product.id,
                "product_uom_qty": qty,
                "location_id": cls.stock_location.id,
                "location_dest_id": cls.stock_location.id,
                "state": "waiting",
            }
        )
        proxy = cls.env["mrp.campaign.demand.proxy"].create(
            {
                "demand_id": demand.id,
                "move_id": move.id,
                "promised_qty": qty,
            }
        )
        return campaign, demand, move, proxy

    @classmethod
    def create_proxy(cls, demand, move, promised_qty):
        """Creates a single proxy."""
        return cls.env["mrp.campaign.demand.proxy"].create(
            {
                "demand_id": demand.id,
                "move_id": move.id,
                "promised_qty": promised_qty,
            }
        )
