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

    def test_add_demands_valid_no_existing_demand(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        move = self.env["stock.move"].create(
            {
                "name": "move",
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": 10,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "state": "waiting",
            }
        )
        self.assertEqual(len(campaign.demand_line_ids), 0)
        self.assertEqual(len(campaign.demand_proxy_ids), 0)

        wizard = (
            self.env["mrp.campaign.add.demand"]
            .with_context(active_id=campaign.id)
            .create({})
        )
        self.assertIn(move, wizard.valid_move_ids)
        wizard.demand_move_ids = move.ids
        wizard.add_demands()
        self.assertEqual(len(campaign.demand_line_ids), 1)
        self.assertEqual(len(campaign.demand_proxy_ids), 1)

    def test_add_demands_valid_with_existing_demand(self) -> None:
        QTY = 6.0
        HALF_QTY = QTY / 2

        campaign = self.create_campaign(self.bulk_material)
        move = self.env["stock.move"].create(
            {
                "name": "move",
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": QTY,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "state": "waiting",
            }
        )

        demand = self.env["mrp.campaign.demand"].create(
            {"campaign_id": campaign.id, "product_id": self.int_prod_x_red.id}
        )

        self.env["mrp.campaign.demand.proxy"].create(
            {"demand_id": demand.id, "move_id": move.id, "promised_qty": HALF_QTY}
        )

        self.assertEqual(len(campaign.demand_line_ids), 1)
        self.assertEqual(len(campaign.demand_proxy_ids), 1)

        wizard = (
            self.env["mrp.campaign.add.demand"]
            .with_context(active_id=campaign.id)
            .create({})
        )
        self.assertIn(move, wizard.valid_move_ids)
        wizard.demand_move_ids = move.ids
        wizard.add_demands()
        self.assertEqual(len(campaign.demand_line_ids), 1)
        self.assertEqual(len(campaign.demand_proxy_ids), 2)

    def test_add_demands_no_added_moves(self) -> None:
        QTY = 6.0

        campaign = self.create_campaign(self.bulk_material)
        move = self.env["stock.move"].create(
            {
                "name": "move",
                "product_id": self.int_prod_x_red.id,
                "product_uom_qty": QTY,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "state": "waiting",
            }
        )

        self.assertEqual(len(campaign.demand_line_ids), 0)
        self.assertEqual(len(campaign.demand_proxy_ids), 0)

        wizard = (
            self.env["mrp.campaign.add.demand"]
            .with_context(active_id=campaign.id)
            .create({})
        )
        self.assertIn(move, wizard.valid_move_ids)
        wizard.demand_move_ids = False
        wizard.add_demands()
        self.assertEqual(len(campaign.demand_line_ids), 0)
        self.assertEqual(len(campaign.demand_proxy_ids), 0)

    def test_multi_company_wizard_isolation(self):
        """Test that the 'Add Demand' wizard only shows moves
        from the campaign's company."""
        company_b = self.env["res.company"].create({"name": "Company B"})
        warehouse_b = self.env["stock.warehouse"].create(
            {"name": "Warehouse B", "code": "WHB", "company_id": company_b.id}
        )

        # Create a move in Company B
        move_b = self.env["stock.move"].create(
            {
                "name": "Move B",
                "product_id": self.bulk_material.id,
                "product_uom_qty": 50.0,
                "location_id": warehouse_b.lot_stock_id.id,
                "location_dest_id": warehouse_b.lot_stock_id.id,
                "company_id": company_b.id,
                "state": "waiting",
            }
        )

        campaign_a = self.create_campaign(self.bulk_material)
        self.assertEqual(campaign_a.company_id, self.env.company)

        # Open the wizard
        action = campaign_a.action_open_add_demand_wizard()
        available_move_ids = action["context"].get("available_move_ids", [])

        self.assertNotIn(
            move_b.id,
            available_move_ids,
            "Moves from Company B should not be available in Company A's campaign",
        )
