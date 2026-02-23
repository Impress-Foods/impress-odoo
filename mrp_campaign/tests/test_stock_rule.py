import logging
from datetime import date, datetime, timedelta

from odoo import fields

from odoo.addons.product.models.product_product import ProductProduct

from ..models.procurement import Procurement
from .test_common import CampaignCase

_logger = logging.getLogger(__name__)


class TestStockRule(CampaignCase):
    @classmethod
    def create_procurement(
        cls, product: ProductProduct, qty: float, values=None
    ) -> Procurement:
        return Procurement(
            product_id=product,
            product_qty=qty,
            product_uom=product.uom_id,
            location_id=cls.stock_location,
            name="Test",
            origin="Tests",
            company_id=cls.company,
            values=values or {},
        )

    def test_run_manufacture_standard_mo(self) -> None:
        """Test that standard manufacture (not campaign) still creates a normal MO."""
        # Ensure it's NOT campaign manufactured
        self.bulk_material.is_campaign_manufactured = False

        procurement = self.create_procurement(
            self.bulk_material,
            100,
            values={
                "bom_id": self.bulk_material.bom_ids[0],
                "date_planned": datetime.now(),
            },
        )
        # We need a rule to pass to _run_manufacture,
        # even if it's a dummy for this unit test
        # since the inherited method might use it.
        rule = self.env["stock.rule"].create(
            {
                "name": "Test Rule",
                "action": "manufacture",
                "picking_type_id": self.env["stock.picking.type"]
                .search([("code", "=", "mrp_operation")], limit=1)
                .id,
                "location_dest_id": self.stock_location.id,
                "route_id": self.env.ref("mrp.route_warehouse0_manufacture").id,
            }
        )

        self.env["stock.rule"]._run_manufacture([(procurement, rule)])

        mos = self.env["mrp.production"].search(
            [("product_id", "=", self.bulk_material.id)]
        )
        self.assertEqual(len(mos), 1, "Should have created 1 standard MO")
        self.assertFalse(
            mos.campaign_id, "Standard MO should not have a campaign assigned"
        )

    def test_run_manufacture_campaign_procurement(self) -> None:
        """Test that campaign manufacture routes to
        mrp.campaign._collect_procurements."""
        self.bulk_material.is_campaign_manufactured = True
        self.bulk_material.is_campaign_anchor = True

        # We need some demand moves to ensure _collect_procurements
        # has something to work with
        # if it tries to sync dates or similar.
        demand_move = self.env["stock.move"].create(
            {
                "name": "Test Demand",
                "product_id": self.bulk_material.id,
                "product_uom_qty": 100,
                "product_uom": self.bulk_material.uom_id.id,
                "location_id": self.env.ref("stock.stock_location_customers").id,
                "location_dest_id": self.stock_location.id,
                "date_deadline": fields.Datetime.to_datetime(
                    date.today() + timedelta(days=5)
                ),
            }
        )

        procurement = self.create_procurement(
            self.bulk_material,
            100,
            values={
                "move_dest_ids": demand_move,
                "bom_id": self.bulk_material.bom_ids[0],
            },
        )

        rule = self.env["stock.rule"].create(
            {
                "name": "Test Rule Campaign",
                "action": "manufacture",
                "picking_type_id": self.env["stock.picking.type"]
                .search([("code", "=", "mrp_operation")], limit=1)
                .id,
                "location_dest_id": self.stock_location.id,
                "route_id": self.env.ref("mrp.route_warehouse0_manufacture").id,
            }
        )

        self.env["stock.rule"]._run_manufacture([(procurement, rule)])

        # Check if a campaign was created
        campaigns = self.env["mrp.campaign"].search(
            [("product_id", "=", self.bulk_material.id)]
        )
        self.assertEqual(len(campaigns), 1, "Should have created 1 campaign")
        self.assertEqual(
            len(campaigns.demand_line_ids), 1, "Campaign should have 1 demand line"
        )
        self.assertIn(
            demand_move,
            campaigns.demand_line_ids.move_dest_ids,
            "Demand move should be linked to campaign",
        )

    def test_get_lead_days_with_visibility_days(self) -> None:
        """Test that visibility_days are correctly added to lead days."""
        rule = self.env["stock.rule"].create(
            {
                "name": "Test Lead Days Rule",
                "action": "manufacture",
                "picking_type_id": self.env["stock.picking.type"]
                .search([("code", "=", "mrp_operation")], limit=1)
                .id,
                "location_dest_id": self.stock_location.id,
                "route_id": self.env.ref("mrp.route_warehouse0_manufacture").id,
            }
        )

        # Test without visibility_days
        delays, _ = rule._get_lead_days(self.bulk_material)
        base_delay = delays.get("total_delay", 0)

        # Test with visibility_days
        delays_v, _ = rule._get_lead_days(self.bulk_material, visibility_days=5)
        self.assertEqual(delays_v["visibility_days"], 5)
        self.assertEqual(delays_v["total_delay"], base_delay + 5)

    def test_orderpoint_lead_days_values(self) -> None:
        """Test that orderpoint correctly includes visibility_days
        in lead days values."""
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company.id)], limit=1
        )
        orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {
                "name": "Test Orderpoint",
                "product_id": self.bulk_material.id,
                "location_id": warehouse.lot_stock_id.id,
                "route_id": self.env.ref("mrp.route_warehouse0_manufacture").id,
                "visibility_days": 7,
            }
        )

        values = orderpoint._get_lead_days_values()
        self.assertEqual(values.get("visibility_days"), 7)

    def test_orderpoint_procurement_date_adjustment(self) -> None:
        """Test that _get_orderpoint_procurement_date subtracts visibility_days."""
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company.id)], limit=1
        )
        orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {
                "name": "Test Orderpoint Date",
                "product_id": self.bulk_material.id,
                "location_id": warehouse.lot_stock_id.id,
                "route_id": self.env.ref("mrp.route_warehouse0_manufacture").id,
                "visibility_days": 10,
                "qty_to_order": 10,
            }
        )

        orderpoint.visibility_days = 0
        date_no_v = orderpoint._get_orderpoint_procurement_date()

        orderpoint.visibility_days = 10
        date_v = orderpoint._get_orderpoint_procurement_date()

        self.assertEqual(date_v, date_no_v - timedelta(days=10))
