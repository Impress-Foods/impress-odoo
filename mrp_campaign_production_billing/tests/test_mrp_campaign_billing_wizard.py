import json
from datetime import date

from odoo.tests.common import TransactionCase


class CampaignBillingCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.groups_id |= cls.env.ref("base.group_user")
        cls.env.user.groups_id |= cls.env.ref("stock.group_stock_manager")
        cls.env.user.groups_id |= cls.env.ref("mrp.group_mrp_manager")
        cls.env.user.groups_id |= cls.env.ref("sales_team.group_sale_salesman")

        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})

        cls.bulk_material = cls.env["product.product"].create(
            {
                "name": "Bulk Material M",
                "type": "product",
                "uom_id": cls.uom_unit.id,
                "uom_po_id": cls.uom_unit.id,
            }
        )
        cls.bulk_material.product_tmpl_id.is_campaign_anchor = True

        cls.billing_product = cls.env["product.product"].create(
            {
                "name": "Billing Service",
                "type": "service",
                "uom_id": cls.uom_unit.id,
            }
        )

        cls.end_prod = cls.env["product.product"].create(
            {
                "name": "End Product",
                "type": "product",
                "uom_id": cls.uom_unit.id,
                "uom_po_id": cls.uom_unit.id,
            }
        )

        cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.end_prod.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
                "billing_product_id": cls.billing_product.id,
                "bom_line_ids": [
                    (0, 0, {"product_id": cls.bulk_material.id, "product_qty": 1.0}),
                ],
            }
        )

    def _create_sale_order(self, billing_product, qty, state="sale"):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "state": state,
            }
        )
        self.env["sale.order.line"].create(
            {
                "order_id": so.id,
                "product_id": billing_product.id,
                "product_uom_qty": qty,
            }
        )
        return so

    def test_wizard_create_with_no_matching_sos(self):
        wizard = self.env["mrp.campaign.wizard.creator"].create(
            {
                "product_id": self.bulk_material.id,
                "planned_date": date.today(),
            }
        )
        wizard._onchange_product_id()
        self.assertEqual(len(json.loads(wizard.available_lines or "[]")), 0)

    def test_wizard_create_with_matching_so(self):
        so = self._create_sale_order(self.billing_product, 10.0)

        wizard = self.env["mrp.campaign.wizard.creator"].create(
            {
                "product_id": self.bulk_material.id,
                "planned_date": date.today(),
            }
        )
        wizard._onchange_product_id()
        lines = json.loads(wizard.available_lines or "[]")
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["id"], so.order_line[0].id)
        self.assertEqual(lines[0]["qty"], 10.0)

    def test_wizard_skips_invoiced_so(self):
        so1 = self._create_sale_order(self.billing_product, 10.0, state="sale")
        so1.invoice_status = "invoiced"
        so2 = self._create_sale_order(self.billing_product, 10.0, state="sale")
        so2.invoice_status = "invoiced"
        so3 = self._create_sale_order(self.billing_product, 5.0, state="sale")
        so3.invoice_status = "invoiced"
        self._create_sale_order(self.billing_product, 7.0, state="sale")

        wizard = self.env["mrp.campaign.wizard.creator"].create(
            {
                "product_id": self.bulk_material.id,
            }
        )
        wizard._onchange_product_id()
        lines = json.loads(wizard.available_lines or "[]")
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["qty"], 7.0)

    def test_wizard_deduplicates_sol(self):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "state": "sale",
            }
        )
        self.env["sale.order.line"].create(
            [
                {
                    "order_id": so.id,
                    "product_id": self.billing_product.id,
                    "product_uom_qty": 10.0,
                },
                {
                    "order_id": so.id,
                    "product_id": self.billing_product.id,
                    "product_uom_qty": 20.0,
                },
            ]
        )

        wizard = self.env["mrp.campaign.wizard.creator"].create(
            {
                "product_id": self.bulk_material.id,
            }
        )
        wizard._onchange_product_id()
        lines = json.loads(wizard.available_lines or "[]")
        self.assertEqual(len(lines), 2)

    def test_confirm_creates_campaign_and_demands(self):
        self._create_sale_order(self.billing_product, 10.0)
        self._create_sale_order(self.billing_product, 5.0)

        wizard = self.env["mrp.campaign.wizard.creator"].create(
            {
                "product_id": self.bulk_material.id,
                "planned_date": date.today(),
            }
        )
        wizard._onchange_product_id()
        lines = json.loads(wizard.available_lines or "[]")
        wizard.selected_line_ids = json.dumps([line["id"] for line in lines])

        action = wizard.process_wizard()
        campaign_id = action.get("res_id")
        campaign = self.env["mrp.campaign"].browse(campaign_id)

        self.assertTrue(campaign.exists())
        self.assertEqual(campaign.product_id, self.bulk_material)
        self.assertEqual(campaign.workflow_type, "production_billing")
        self.assertEqual(len(campaign.demand_line_ids), 2)
        for demand in campaign.demand_line_ids:
            self.assertEqual(demand.product_id, self.end_prod)
            billing_targets = self.env["mrp.campaign.demand.target"].search(
                [("demand_id", "=", demand.id), ("target_type", "=", "billing")]
            )
            self.assertEqual(len(billing_targets), 1)

    def test_confirm_creates_demands_on_existing_campaign(self):
        self._create_sale_order(self.billing_product, 10.0)
        self._create_sale_order(self.billing_product, 5.0)

        campaign = self.env["mrp.campaign"].create(
            {
                "product_id": self.bulk_material.id,
                "workflow_type": "production_billing",
            }
        )

        wizard = (
            self.env["mrp.campaign.wizard.creator"]
            .with_context(default_campaign_id=campaign.id)
            .create({})
        )
        self.assertEqual(wizard.campaign_id, campaign)
        self.assertEqual(wizard.product_id, self.bulk_material)
        wizard._onchange_product_id()
        lines = json.loads(wizard.available_lines or "[]")
        self.assertEqual(len(lines), 2)
        wizard.selected_line_ids = json.dumps([line["id"] for line in lines])

        wizard.process_wizard()

        self.assertEqual(len(campaign.demand_line_ids), 2)

    def test_confirm_preserves_existing_demands(self):
        self._create_sale_order(self.billing_product, 10.0)

        campaign = self.env["mrp.campaign"].create(
            {
                "product_id": self.bulk_material.id,
                "workflow_type": "production_billing",
            }
        )
        existing_demand = self.env["mrp.campaign.demand"].create(
            {
                "campaign_id": campaign.id,
                "product_id": self.end_prod.id,
                "target_qty": 5.0,
            }
        )

        wizard = (
            self.env["mrp.campaign.wizard.creator"]
            .with_context(default_campaign_id=campaign.id)
            .create({})
        )
        wizard._onchange_product_id()
        lines = json.loads(wizard.available_lines or "[]")
        wizard.selected_line_ids = json.dumps([line["id"] for line in lines])
        wizard.process_wizard()

        self.assertEqual(len(campaign.demand_line_ids), 2)
        self.assertIn(existing_demand, campaign.demand_line_ids)
        self.assertEqual(existing_demand.target_qty, 5.0)

    def test_confirm_with_no_selection_creates_nothing(self):
        wizard = self.env["mrp.campaign.wizard.creator"].create(
            {
                "product_id": self.bulk_material.id,
                "planned_date": date.today(),
            }
        )
        wizard._onchange_product_id()
        self.assertEqual(len(json.loads(wizard.available_lines or "[]")), 0)

        action = wizard.process_wizard()
        campaign_id = action.get("res_id")
        campaign = self.env["mrp.campaign"].browse(campaign_id)
        self.assertTrue(campaign.exists())
        self.assertEqual(len(campaign.demand_line_ids), 0)

    def test_confirm_with_no_selected_lines_ignores_them(self):
        self._create_sale_order(self.billing_product, 10.0)

        wizard = self.env["mrp.campaign.wizard.creator"].create(
            {
                "product_id": self.bulk_material.id,
                "planned_date": date.today(),
            }
        )
        wizard._onchange_product_id()
        lines = json.loads(wizard.available_lines or "[]")
        self.assertEqual(len(lines), 1)
        wizard.selected_line_ids = "[]"

        action = wizard.process_wizard()
        campaign_id = action.get("res_id")
        campaign = self.env["mrp.campaign"].browse(campaign_id)
        self.assertTrue(campaign.exists())
        self.assertEqual(len(campaign.demand_line_ids), 0)
