from .test_common import CampaignCase


class TestWizardAddDemand(CampaignCase):
    def test_get_valid_move_ids(self) -> None:
        moves = self.env["stock.move"].create(
            [
                {
                    "name": "move_1",
                    "product_id": self.end_prod_b_blue.id,
                    "product_uom_qty": 20,
                    "location_id": self.stock_location.id,
                    "location_dest_id": self.stock_location.id,
                    "state": "waiting",
                },
                {
                    "name": "move_2",
                    "product_id": self.end_prod_b_red.id,
                    "product_uom_qty": 20,
                    "location_id": self.stock_location.id,
                    "location_dest_id": self.stock_location.id,
                    "state": "waiting",
                },
            ]
        )
        # Create some invalid moves
        self.env["stock.move"].create(
            [
                {
                    "name": "move_1",
                    "product_id": self.end_prod_b_blue.id,
                    "product_uom_qty": 20,
                    "location_id": self.stock_location.id,
                    "location_dest_id": self.stock_location.id,
                    "state": "done",
                },
                {
                    "name": "move_2",
                    "product_id": self.product_no_bom.id,
                    "product_uom_qty": 20,
                    "location_id": self.stock_location.id,
                    "location_dest_id": self.stock_location.id,
                    "state": "waiting",
                },
            ]
        )

        campaign = self.create_campaign(self.bulk_material)
        move_ids = self.env["mrp.campaign.add.demand"]._get_valid_move_ids(campaign)
        self.assertCountEqual(move_ids.ids, moves.ids)
