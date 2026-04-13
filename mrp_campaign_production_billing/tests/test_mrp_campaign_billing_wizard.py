import json
from datetime import date

from odoo.tests.common import TransactionCase


class CampaignBillingCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids |= cls.env.ref("base.group_user")
        cls.env.user.group_ids |= cls.env.ref("stock.group_stock_manager")
        cls.env.user.group_ids |= cls.env.ref("mrp.group_mrp_manager")
        cls.env.user.group_ids |= cls.env.ref("sales_team.group_sale_salesman")

        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})

        cls.bulk_material = cls.env["product.product"].create(
            {
                "name": "Bulk Material M",
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.uom_unit.id,
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
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.uom_unit.id,
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

        cls.create_wizard = cls.env["mrp.campaign.wizard.creator"].with_context(
            default_workflow_type="production_billing"
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
        wizard = self.create_wizard.create(
            {
                "product_id": self.bulk_material.id,
                "planned_date": date.today(),
            }
        )
        wizard._onchange_product_id()
        self.assertEqual(len(json.loads(wizard.available_lines or "[]")), 0)

    def test_wizard_create_with_matching_so(self):
        so = self._create_sale_order(self.billing_product, 10.0)

        wizard = self.create_wizard.create(
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

        wizard = self.create_wizard.create(
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

        wizard = self.create_wizard.create(
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

        wizard = self.create_wizard.create(
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
                [
                    ("demand_id", "=", demand.id),
                    ("workflow_type", "=", "production_billing"),
                ]
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

        wizard = self.create_wizard.with_context(
            default_campaign_id=campaign.id
        ).create({})
        self.assertEqual(wizard.campaign_id, campaign)
        self.assertEqual(wizard.product_id, self.bulk_material)
        wizard._onchange_product_id()
        lines = json.loads(wizard.available_lines or "[]")
        self.assertEqual(len(lines), 2)
        wizard.selected_line_ids = json.dumps([line["id"] for line in lines])

        wizard.process_wizard()

        self.assertEqual(len(campaign.demand_line_ids), 2)

    def test_confirm_with_no_selection_creates_nothing(self):
        wizard = self.create_wizard.create(
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

        wizard = self.create_wizard.create(
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

    def test_available_lines_deduplicates_shared_bom_variants(self):
        """Two variants sharing the same BoM must not produce duplicate SOL IDs."""
        color_attr = self.env["product.attribute"].create({"name": "Color"})
        color_red = self.env["product.attribute.value"].create(
            {"name": "Red", "attribute_id": color_attr.id}
        )
        color_blue = self.env["product.attribute.value"].create(
            {"name": "Blue", "attribute_id": color_attr.id}
        )

        # New anchor product for this test
        anchor = self.env["product.product"].create(
            {
                "name": "Test Anchor",
                "type": "consu",
                "is_storable": True,
                "uom_id": self.uom_unit.id,
            }
        )
        anchor.product_tmpl_id.is_campaign_anchor = True

        # Intermediate product with BoM -> anchor
        intermediate = self.env["product.product"].create(
            {
                "name": "Test Intermediate",
                "type": "consu",
                "is_storable": True,
                "uom_id": self.uom_unit.id,
            }
        )
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": intermediate.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (0, 0, {"product_id": anchor.id, "product_qty": 1.0}),
                ],
            }
        )

        # End product template with two variants (created with attributes)
        end_tmpl = self.env["product.template"].create(
            {
                "name": "Test Multi Variant End",
                "type": "consu",
                "is_storable": True,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": color_attr.id,
                            "value_ids": [(6, 0, [color_red.id, color_blue.id])],
                        },
                    ),
                ],
            }
        )
        self.assertEqual(len(end_tmpl.product_variant_ids), 2)

        # Shared BoM for the template with a new billing product
        billing_2 = self.env["product.product"].create(
            {
                "name": "Billing Service 2",
                "type": "service",
                "uom_id": self.uom_unit.id,
            }
        )
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": end_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                "billing_product_id": billing_2.id,
                "bom_line_ids": [
                    (0, 0, {"product_id": intermediate.id, "product_qty": 1.0}),
                ],
            }
        )

        so = self._create_sale_order(billing_2, 10.0)

        wizard = self.create_wizard.create(
            {
                "product_id": anchor.id,
            }
        )
        wizard._onchange_product_id()
        lines = json.loads(wizard.available_lines or "[]")

        # Should be 1 entry (one SOL), not 2 (one per variant sharing the BoM)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["id"], so.order_line[0].id)

    def test_available_lines_shows_both_variant_billing_products(self):
        """Each variant with its own BoM must surface its own billing product."""
        color_attr = self.env["product.attribute"].create({"name": "Color"})
        color_red = self.env["product.attribute.value"].create(
            {"name": "Red", "attribute_id": color_attr.id}
        )
        color_blue = self.env["product.attribute.value"].create(
            {"name": "Blue", "attribute_id": color_attr.id}
        )

        anchor = self.env["product.product"].create(
            {
                "name": "Test Anchor 2",
                "type": "consu",
                "is_storable": True,
                "uom_id": self.uom_unit.id,
            }
        )
        anchor.product_tmpl_id.is_campaign_anchor = True

        intermediate = self.env["product.product"].create(
            {
                "name": "Test Intermediate 2",
                "type": "consu",
                "is_storable": True,
                "uom_id": self.uom_unit.id,
            }
        )
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": intermediate.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (0, 0, {"product_id": anchor.id, "product_qty": 1.0}),
                ],
            }
        )

        end_tmpl = self.env["product.template"].create(
            {
                "name": "Test Variant Specific End",
                "type": "consu",
                "is_storable": True,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": color_attr.id,
                            "value_ids": [(6, 0, [color_red.id, color_blue.id])],
                        },
                    ),
                ],
            }
        )
        variant_red = end_tmpl.product_variant_ids.filtered(
            lambda p: (
                color_red
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )
        variant_blue = end_tmpl.product_variant_ids.filtered(
            lambda p: (
                color_blue
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )
        self.assertEqual(len(end_tmpl.product_variant_ids), 2)

        billing_a = self.env["product.product"].create(
            {"name": "Billing A", "type": "service", "uom_id": self.uom_unit.id}
        )
        billing_b = self.env["product.product"].create(
            {"name": "Billing B", "type": "service", "uom_id": self.uom_unit.id}
        )

        # Variant-specific BoMs (product_id set, not just product_tmpl_id)
        self.env["mrp.bom"].create(
            {
                "product_id": variant_red.id,
                "product_tmpl_id": end_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                "billing_product_id": billing_a.id,
                "bom_line_ids": [
                    (0, 0, {"product_id": intermediate.id, "product_qty": 1.0}),
                ],
            }
        )
        self.env["mrp.bom"].create(
            {
                "product_id": variant_blue.id,
                "product_tmpl_id": end_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                "billing_product_id": billing_b.id,
                "bom_line_ids": [
                    (0, 0, {"product_id": intermediate.id, "product_qty": 1.0}),
                ],
            }
        )

        so = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "state": "sale"}
        )
        self.env["sale.order.line"].create(
            [
                {
                    "order_id": so.id,
                    "product_id": billing_a.id,
                    "product_uom_qty": 10.0,
                },
                {
                    "order_id": so.id,
                    "product_id": billing_b.id,
                    "product_uom_qty": 20.0,
                },
            ]
        )

        wizard = self.create_wizard.create({"product_id": anchor.id})
        wizard._onchange_product_id()
        lines = json.loads(wizard.available_lines or "[]")

        # Both billing products must appear (one per variant's own BoM)
        self.assertEqual(len(lines), 2)
        line_ids = {line["id"] for line in lines}
        self.assertEqual(line_ids, {so.order_line[0].id, so.order_line[1].id})

    def test_valid_sources_includes_variant_billing_products(self):
        """_get_valid_sources must return SOLs for all variant-specific billing prod."""
        color_attr = self.env["product.attribute"].create({"name": "Color"})
        color_red = self.env["product.attribute.value"].create(
            {"name": "Red", "attribute_id": color_attr.id}
        )
        color_blue = self.env["product.attribute.value"].create(
            {"name": "Blue", "attribute_id": color_attr.id}
        )

        anchor = self.env["product.product"].create(
            {
                "name": "Test Anchor 3",
                "type": "consu",
                "is_storable": True,
                "uom_id": self.uom_unit.id,
            }
        )
        anchor.product_tmpl_id.is_campaign_anchor = True

        intermediate = self.env["product.product"].create(
            {
                "name": "Test Intermediate 3",
                "type": "consu",
                "is_storable": True,
                "uom_id": self.uom_unit.id,
            }
        )
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": intermediate.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (0, 0, {"product_id": anchor.id, "product_qty": 1.0}),
                ],
            }
        )

        end_tmpl = self.env["product.template"].create(
            {
                "name": "Test Valid Sources End",
                "type": "consu",
                "is_storable": True,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": color_attr.id,
                            "value_ids": [(6, 0, [color_red.id, color_blue.id])],
                        },
                    ),
                ],
            }
        )
        variant_red = end_tmpl.product_variant_ids.filtered(
            lambda p: (
                color_red
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )
        variant_blue = end_tmpl.product_variant_ids.filtered(
            lambda p: (
                color_blue
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )

        billing_x = self.env["product.product"].create(
            {"name": "Billing X", "type": "service", "uom_id": self.uom_unit.id}
        )
        billing_y = self.env["product.product"].create(
            {"name": "Billing Y", "type": "service", "uom_id": self.uom_unit.id}
        )

        self.env["mrp.bom"].create(
            {
                "product_id": variant_red.id,
                "product_tmpl_id": end_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                "billing_product_id": billing_x.id,
                "bom_line_ids": [
                    (0, 0, {"product_id": intermediate.id, "product_qty": 1.0}),
                ],
            }
        )
        self.env["mrp.bom"].create(
            {
                "product_id": variant_blue.id,
                "product_tmpl_id": end_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                "billing_product_id": billing_y.id,
                "bom_line_ids": [
                    (0, 0, {"product_id": intermediate.id, "product_qty": 1.0}),
                ],
            }
        )

        so = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "state": "sale"}
        )
        self.env["sale.order.line"].create(
            [
                {
                    "order_id": so.id,
                    "product_id": billing_x.id,
                    "product_uom_qty": 5.0,
                },
                {
                    "order_id": so.id,
                    "product_id": billing_y.id,
                    "product_uom_qty": 8.0,
                },
            ]
        )

        wizard = self.create_wizard.create({"product_id": anchor.id})
        valid = wizard._get_valid_sources()
        valid_products = set(valid.mapped("product_id").ids)

        # Both billing products must be in valid sources
        self.assertIn(billing_x.id, valid_products)
        self.assertIn(billing_y.id, valid_products)
