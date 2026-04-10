from odoo.exceptions import ValidationError

from ..models.mrp_campaign import MrpCampaign
from ..models.mrp_campaign_line import CampaignLine
from .test_common import CampaignCase


class TestMrpCampaignLine(CampaignCase):
    def test_compute_is_batch_produced(self):
        line_bulk = self.create_line(self.bulk_material)
        line_end = self.create_line(self.int_prod_x_red)
        self.assertTrue(line_bulk.is_batch_produced)
        self.assertFalse(line_end.is_batch_produced)

    def test_batch_size(self) -> None:
        campaign: MrpCampaign = self.create_campaign(self.bulk_material)
        line: CampaignLine = self.create_line(self.bulk_material, campaign)
        campaign.override_batch_size = False
        campaign.batch_size = 20.0
        self.assertEqual(line.batch_size, self.bulk_material.mrp_max_batch_size)

    def test_batch_size_override(self) -> None:
        campaign: MrpCampaign = self.create_campaign(self.bulk_material)
        line: CampaignLine = self.create_line(self.bulk_material, campaign)
        campaign.override_batch_size = True
        campaign.batch_size = 20.0
        self.assertEqual(line.batch_size, campaign.batch_size)

    def test_get_downstream_product_anchor(self) -> None:
        line: CampaignLine = self.create_line(self.bulk_material)
        self.assertEqual(self.env["product.product"], line.downstream_product_id)

    def test_get_downstream_product_single_level(self) -> None:
        line: CampaignLine = self.create_line(self.int_prod_x_red)
        self.assertEqual(line.downstream_product_id, self.bulk_material)

    def test_get_downstream_product_multi_level(self) -> None:
        line: CampaignLine = self.create_line(self.end_prod_a_red)
        self.assertEqual(line.downstream_product_id, self.int_prod_x_red)

    def test_get_downstream_product_multiple_anchor(self) -> None:
        alt_bulk = self.env["product.product"].create(
            {
                "name": "Bulk Material Alt",
                "type": "consu",
                "is_storable": True,
                "mrp_max_batch_size": 1000.0,
                "campaign_buffer_percent": 0.05,
            }
        )
        alt_bulk.product_tmpl_id.is_campaign_anchor = True

        int_prod = self.env["product.product"].create(
            {
                "name": "Intermediate Product Alt",
                "type": "consu",
                "is_storable": True,
            }
        )

        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": int_prod.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (0, 0, {"product_id": self.bulk_material.id, "product_qty": 3.0}),
                    (0, 0, {"product_id": alt_bulk.id, "product_qty": 3.0}),
                ],
            }
        )
        line = self.create_line(int_prod)
        with self.assertRaises(ValidationError) as _cm:
            _ = line.downstream_product_id

    def test_get_downstream_product_bomless_line(self) -> None:
        line = self.create_line(self.product_no_bom)
        self.assertEqual(self.env["product.product"], line.downstream_product_id)

    def test_get_downstream_product_no_anchor_in_tree(self) -> None:
        component = self.env["product.product"].create(
            {"name": "Component Product", "type": "consu", "is_storable": True}
        )
        anchorless_prod = self.env["product.product"].create(
            {"name": "Anchor-less Product", "type": "consu", "is_storable": True}
        )

        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": anchorless_prod.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (0, 0, {"product_id": component.id, "product_qty": 3.0}),
                ],
            }
        )

        line = self.create_line(anchorless_prod)
        with self.assertRaises(ValidationError) as _cm:
            _ = line.downstream_product_id

    def test_get_downstream_product_no_valid_bom_lines(self) -> None:
        int_tmpl = self.env["product.template"].create(
            {
                "name": "Intermediate Product Alt",
                "type": "consu",
                "is_storable": True,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": self.color_attribute.id,
                            "value_ids": [
                                (6, 0, [self.color_green.id, self.color_red.id])
                            ],
                        },
                    )
                ],
            }
        )
        int_prod_green = int_tmpl.product_variant_ids.filtered(
            lambda p: (
                self.color_green
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )
        int_prod_red = int_tmpl.product_variant_ids.filtered(
            lambda p: (
                self.color_red
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )
        ptav_green = (
            int_prod_green.attribute_line_ids.product_template_value_ids.filtered(
                lambda p: p.product_attribute_value_id == self.color_green
            )
        )

        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": int_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.bulk_material.id,
                            "product_qty": 3.0,
                            "bom_product_template_attribute_value_ids": [ptav_green.id],
                        },
                    ),
                ],
            }
        )

        line = self.create_line(int_prod_red)
        with self.assertRaises(ValidationError) as _cm:
            _ = line.downstream_product_id

    def test_compute_fulfilled_qty(self) -> None:
        line: CampaignLine = self.create_line(self.bulk_material)
        mos = self.env["mrp.production"].create(
            [
                {
                    "product_id": self.bulk_material.id,
                    "product_qty": 100.0,
                    "campaign_line_id": line.id,
                }
                for _i in range(3)
            ]
        )
        mos.action_confirm()
        mos.write({"qty_producing": 100.0})

        # 3 MOs, 1 confirmed, 1 done, 1 cancelled.
        # Produced qty should be 100.0 units

        mos[0].button_mark_done()
        mos[1].action_cancel()
        self.assertEqual(line.fulfilled_qty, 100.0)

    def test_compute_qty_w_demand_no_buffers(self) -> None:
        QTY = 100.0
        campaign: MrpCampaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.end_prod_b_red, QTY, campaign)
        campaign._construct_tree_from_demand(False)

        self.assertEqual(len(campaign.line_ids), 1)
        self.assertEqual(len(campaign.demand_line_ids), 1)

        campaign_line: CampaignLine = campaign.line_ids[0]
        self.assertEqual(QTY, campaign_line.qty)

    def test_compute_qty_w_demand_w_buffers(self) -> None:
        BUFFER_MULT = 1.05  # 5% more
        QTY = 100
        campaign: MrpCampaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.bulk_material, QTY, campaign)
        campaign._construct_tree_from_demand(False)

        self.assertEqual(len(campaign.line_ids), 1)
        self.assertEqual(len(campaign.demand_line_ids), 1)

        campaign_line: CampaignLine = campaign.line_ids[0]

        self.assertEqual(QTY * BUFFER_MULT, campaign_line.qty)

    def test_compute_qty_w_upstream_no_buffers(self) -> None:
        QTY = 100.0
        # factor: 2.0 x 1.0 = 2.0 (see bom_end_prod_b)
        FACTOR = 2.0

        campaign: MrpCampaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.end_prod_b_red, QTY, campaign)
        campaign._construct_tree_from_demand()
        self.assertEqual(len(campaign.line_ids), 3)

        intermediate_line: CampaignLine = campaign.line_ids.filtered_domain(
            [("product_id", "=", self.int_prod_y_red.id)]
        )
        self.assertEqual(len(intermediate_line), 1)

        self.assertEqual(intermediate_line.qty, FACTOR * QTY)

    def test_compute_qty_w_upstream_w_buffers(self) -> None:
        QTY = 100.0
        # factor: 1.0 x 3.0 = 6.0 (see bom_end_prod_b, bom_int_prod_y)
        FACTOR = 3.0
        BUFFER_MULT = 1.05  # 5% more

        campaign: MrpCampaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.int_prod_y_red, QTY, campaign)
        campaign._construct_tree_from_demand()
        self.assertEqual(len(campaign.line_ids), 2)

        bulk_line: CampaignLine = campaign.line_ids.filtered_domain(
            [("product_id", "=", self.bulk_material.id)]
        )

        self.assertEqual(len(bulk_line), 1)

        self.assertEqual(bulk_line.qty, FACTOR * QTY * BUFFER_MULT)

    def test_compute_producing_qty(self) -> None:
        line = self.create_line(self.bulk_material)
        mos = self.env["mrp.production"].create(
            [
                {
                    "product_id": self.bulk_material.id,
                    "product_qty": 100.0,
                    "campaign_line_id": line.id,
                }
                for _i in range(3)
            ]
        )
        mos.action_confirm()
        mos.write({"qty_producing": 100.0})
        mos[0].button_mark_done()
        mos[1].action_cancel()
        # 3 MOs, 1 confirmed, 1 done, 1 cancelled.
        # Producing qty should be 200.0 units
        self.assertEqual(line.producing_qty, 200.0)

    def test_construct_downstream_tree_line_anchor(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        line = self.create_line(self.bulk_material, campaign)

        self.assertEqual(len(campaign.line_ids), 1)

        line._construct_downstream_tree_line()

        self.assertEqual(len(campaign.line_ids), 1)
        self.assertFalse(line.downstream_line_id)

    def test_construct_downstream_tree_line_intermediate(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        line = self.create_line(self.int_prod_x_red, campaign)

        self.assertEqual(len(campaign.line_ids), 1)

        line._construct_downstream_tree_line()

        self.assertEqual(len(campaign.line_ids), 2)
        anchor_line = campaign.line_ids.filtered_domain(
            [("product_id", "=", campaign.product_id.id)]
        )
        self.assertEqual(len(anchor_line), 1)
        self.assertEqual(line.downstream_line_id, anchor_line)

    def test_construct_downstream_tree_line_end(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        line = self.create_line(self.end_prod_a_red, campaign)

        self.assertEqual(len(campaign.line_ids), 1)

        line._construct_downstream_tree_line()

        self.assertEqual(len(campaign.line_ids), 3)
        anchor_line = campaign.line_ids.filtered_domain(
            [("product_id", "=", campaign.product_id.id)]
        )
        intermediate_line = campaign.line_ids.filtered_domain(
            [("product_id", "=", self.int_prod_x_red.id)]
        )
        self.assertEqual(len(intermediate_line), 1)
        self.assertEqual(line.downstream_line_id, intermediate_line)
        self.assertEqual(len(anchor_line), 1)
        self.assertEqual(intermediate_line.downstream_line_id, anchor_line)

    def test_construct_downstream_tree_line_multiple_end(self) -> None:
        campaign = self.create_campaign(self.bulk_material)

        line_end_red = self.create_line(self.end_prod_a_red, campaign)
        line_end_blue = self.create_line(self.end_prod_a_blue, campaign)

        self.assertEqual(len(campaign.line_ids), 2)

        line_end_blue._construct_downstream_tree_line()
        line_end_red._construct_downstream_tree_line()

        self.assertEqual(len(campaign.line_ids), 5)
        anchor_line = campaign.line_ids.filtered_domain(
            [("product_id", "=", campaign.product_id.id)]
        )
        intermediate_line_red = campaign.line_ids.filtered_domain(
            [("product_id", "=", self.int_prod_x_red.id)]
        )
        intermediate_line_blue = campaign.line_ids.filtered_domain(
            [("product_id", "=", self.int_prod_x_blue.id)]
        )
        self.assertEqual(len(intermediate_line_red), 1)
        self.assertEqual(len(intermediate_line_blue), 1)

        self.assertEqual(line_end_red.downstream_line_id, intermediate_line_red)
        self.assertEqual(line_end_blue.downstream_line_id, intermediate_line_blue)

        self.assertEqual(len(anchor_line), 1)
        self.assertEqual(intermediate_line_red.downstream_line_id, anchor_line)
        self.assertEqual(intermediate_line_blue.downstream_line_id, anchor_line)

    def test_construct_downstream_tree_line_no_bom(self) -> None:
        campaign = self.create_campaign(self.bulk_material)
        line = self.create_line(self.product_no_bom, campaign)
        line._construct_downstream_tree_line()

    def test_is_valid_bom_line_for_product_valid_attribute(self) -> None:
        line = self.create_line(self.end_prod_a_red)
        bom_line = self.bom_end_prod_a.bom_line_ids.filtered(
            lambda x: (
                self.ptav_end_prod_a_red.id
                in x.bom_product_template_attribute_value_ids.ids
            )
        )[0]

        self.assertTrue(line.is_valid_bom_line_for_product(bom_line))

    def test_is_valid_bom_line_for_product_invalid_attribute(self) -> None:
        line = self.create_line(self.end_prod_a_red)
        bom_line = self.bom_end_prod_a.bom_line_ids.filtered(
            lambda x: (
                self.ptav_end_prod_a_blue.id
                in x.bom_product_template_attribute_value_ids.ids
            )
        )[0]

        self.assertFalse(line.is_valid_bom_line_for_product(bom_line))

    def test_is_valid_bom_line_for_product_wrong_product(self) -> None:
        line = self.create_line(self.end_prod_a_red)
        bom_line = self.bom_end_prod_b.bom_line_ids[0]
        self.assertFalse(line.is_valid_bom_line_for_product(bom_line))

    def test_is_valid_bom_line_for_product_no_attribute_valid(self) -> None:
        line = self.create_line(self.int_prod_x_red)
        bom_line = self.bom_int_prod_x.bom_line_ids[0]
        self.assertTrue(line.is_valid_bom_line_for_product(bom_line))

    def test_is_valid_bom_line_for_product_no_attribute_invalid(self) -> None:
        line = self.create_line(self.int_prod_x_red)
        bom_line = self.bom_int_prod_y.bom_line_ids[0]
        self.assertFalse(line.is_valid_bom_line_for_product(bom_line))

    def test_get_factor_anchor_anchor_product(self) -> None:
        line = self.create_line(self.bulk_material)
        self.assertEqual(line._get_anchor_factor(), 1)

    def test_get_factor_anchor_no_ds_product(self) -> None:
        line = self.create_line(self.product_no_bom)
        self.assertEqual(line._get_anchor_factor(), 1)

    def test_get_factor_anchor_int_product(self) -> None:
        FACTOR = 1.0 * 3.0
        campaign = self.create_campaign(self.bulk_material)
        line = self.create_line(self.int_prod_x_blue, campaign)

        line._construct_downstream_tree_line()
        self.assertEqual(line.downstream_product_id.id, self.bulk_material.id)
        self.assertEqual(line._get_anchor_factor(), FACTOR)

    def test_get_factor_anchor_end_product(self) -> None:
        FACTOR = 1.0 * 3.0 * 2.0
        campaign = self.create_campaign(self.bulk_material)
        line = self.create_line(self.end_prod_b_red, campaign)
        line._construct_downstream_tree_line()
        self.assertEqual(line.downstream_product_id.id, self.int_prod_y_red.id)
        self.assertEqual(line._get_anchor_factor(), FACTOR)

    def test_make_production_order_normal(self) -> None:
        QTY = 100.0
        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.int_prod_y_blue, QTY, campaign)
        campaign._construct_tree_from_demand(False)
        self.assertEqual(len(campaign.line_ids), 1)
        line = campaign.line_ids
        line.make_production_order()
        self.assertEqual(len(line.production_ids), 1)
        self.assertCountEqual([QTY], line.production_ids.mapped("product_qty"))

    def test_make_production_order_batch_larger(self) -> None:
        QTY = 2500.0
        campaign = self.create_campaign(self.bulk_material)
        campaign.buffer_percent = 0.0
        self.create_demand(self.bulk_material, QTY, campaign)

        campaign._construct_tree_from_demand(False)
        self.assertEqual(len(campaign.line_ids), 1)
        line = campaign.line_ids
        line.make_production_order()
        self.assertEqual(len(line.production_ids), 3)  # 2x1000.0 + 1x500.0
        self.assertCountEqual(
            [1000.0, 500.0, 1000.0], line.production_ids.mapped("product_qty")
        )

    def test_make_production_order_batch_exact(self) -> None:
        QTY = 1000.0
        campaign = self.create_campaign(self.bulk_material)
        campaign.buffer_percent = 0.0
        self.create_demand(self.bulk_material, QTY, campaign)

        campaign._construct_tree_from_demand(False)
        self.assertEqual(len(campaign.line_ids), 1)
        line = campaign.line_ids
        line.make_production_order()
        self.assertEqual(len(line.production_ids), 1)  # 1x1000.0
        self.assertCountEqual([1000.0], line.production_ids.mapped("product_qty"))

    def test_make_production_order_batch_under(self) -> None:
        QTY = 750.0
        campaign = self.create_campaign(self.bulk_material)
        campaign.buffer_percent = 0.0
        self.create_demand(self.bulk_material, QTY, campaign)

        campaign._construct_tree_from_demand(False)
        self.assertEqual(len(campaign.line_ids), 1)
        line = campaign.line_ids
        line.make_production_order()
        self.assertEqual(len(line.production_ids), 1)  # 1x750.0
        self.assertCountEqual([750.0], line.production_ids.mapped("product_qty"))

    def test_batch_size_zero_as_infinite(self):
        """Test that batch_size=0 creates only one MO for the entire quantity."""
        QTY = 2500.0
        campaign = self.create_campaign(self.bulk_material)
        campaign.override_batch_size = True
        campaign.batch_size = 0.0
        campaign.buffer_percent = 0.0
        self.create_demand(self.bulk_material, QTY, campaign)

        campaign.action_plan()
        line = campaign.line_ids.filtered(
            lambda line: line.product_id == self.bulk_material
        )
        self.assertEqual(
            len(line.production_ids),
            1,
            "Should have created only one MO for infinite batch size",
        )
        self.assertEqual(line.production_ids.product_qty, QTY)

    def test_out_of_sync_detection_and_sync_button(self):
        """Test that changing MO quantity triggers out_of_sync
        and action_sync_line fixes it."""
        QTY = 100.0
        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.bulk_material, QTY, campaign)
        campaign.action_plan()

        line = campaign.line_ids[0]
        self.assertFalse(line.is_out_of_sync)
        self.assertFalse(campaign.is_out_of_sync)

        # Manually change MO quantity
        mo = line.production_ids[0]
        mo.product_qty = QTY + 10.0

        # Accessing computed fields to trigger recompute
        self.assertTrue(
            line.is_out_of_sync, "Line should be out of sync after MO quantity change"
        )
        self.assertTrue(
            campaign.is_out_of_sync,
            "Campaign should be out of sync after MO quantity change",
        )

        # Resolve via sync button
        line.action_sync_line()
        self.assertFalse(line.is_out_of_sync, "Line should be back in sync")
        self.assertEqual(
            mo.product_qty,
            QTY * 1.05,
            "MO quantity should have been adjusted back (including buffer)",
        )

    def test_get_factor_to_product_uom_conversion(self) -> None:
        # Create a product with a different UoM category
        uom_unit = self.env.ref("uom.product_uom_unit")
        uom_kg = self.env.ref("uom.product_uom_kgm")
        uom_gram = self.env.ref("uom.product_uom_gram")

        product_parent = self.env["product.product"].create(
            {
                "name": "Product Parent",
                "type": "consu",
                "is_storable": True,
                "uom_id": uom_unit.id,
            }
        )
        product_component = self.env["product.product"].create(
            {
                "name": "Product Component",
                "type": "consu",
                "is_storable": True,
                "uom_id": uom_kg.id,
            }
        )

        # BoM for 1 Unit of Product Parent, uses 500 grams of Product Component
        bom = self.env["mrp.bom"].create(
            {
                "product_tmpl_id": product_parent.product_tmpl_id.id,
                "product_qty": 1.0,
                "product_uom_id": uom_unit.id,
                "type": "normal",
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product_component.id,
                            "product_qty": 500.0,
                            "product_uom_id": uom_gram.id,
                        },
                    ),
                ],
            }
        )

        # factor should be (500g -> 0.5kg) / (1 Unit -> 1 Unit) = 0.5
        factor = bom.get_factor_to_product(product_component)
        self.assertEqual(factor, 0.5)

    def test_kit_bom_guard(self) -> None:
        parent_product = self.env["product.product"].create(
            {
                "name": "Kit Product",
                "type": "consu",
                "is_storable": True,
            }
        )

        kit_product = self.env["product.product"].create(
            {
                "name": "Kit Product",
                "type": "consu",
                "is_storable": True,
            }
        )
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": parent_product.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (0, 0, {"product_id": kit_product.id, "product_qty": 1.0}),
                ],
            }
        )
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": kit_product.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "phantom",
                "bom_line_ids": [
                    (0, 0, {"product_id": self.bulk_material.id, "product_qty": 1.0}),
                ],
            }
        )

        campaign = self.create_campaign(self.bulk_material)
        line = self.create_line(parent_product, campaign)
        kit_line = self.create_line(kit_product, campaign)

        with self.assertRaisesRegex(
            ValidationError,
            r"Kits \(Phantom BoMs\) are not supported in manufacturing campaigns",
        ):
            kit_line._get_downstream_product()

        with self.assertRaisesRegex(
            ValidationError,
            r"Kits \(Phantom BoMs\) are not supported in manufacturing campaigns",
        ):
            line._construct_downstream_tree_line()

    def test_zero_anchor_error(self) -> None:
        # Product with BoM but no anchor in its lineage
        component = self.env["product.product"].create(
            {
                "name": "Component",
                "type": "consu",
                "is_storable": True,
            }
        )
        product_no_anchor = self.env["product.product"].create(
            {
                "name": "No Anchor Product",
                "type": "consu",
                "is_storable": True,
            }
        )
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": product_no_anchor.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (0, 0, {"product_id": component.id, "product_qty": 1.0}),
                ],
            }
        )

        campaign = self.create_campaign(self.bulk_material)
        line = self.create_line(product_no_anchor, campaign)

        with self.assertRaisesRegex(
            ValidationError, "Could not resolve downstream product"
        ):
            line._get_downstream_product()

    def test_construct_downstream_tree_variant_only_bom(self) -> None:
        """Products with only a variant-specific BoM must still appear in tree."""
        color_attr = self.env["product.attribute"].create({"name": "Color"})
        color_red = self.env["product.attribute.value"].create(
            {"name": "Red", "attribute_id": color_attr.id}
        )
        color_blue = self.env["product.attribute.value"].create(
            {"name": "Blue", "attribute_id": color_attr.id}
        )

        # Intermediate with variant-specific BoM (product_id set, no template BoM)
        int_tmpl = self.env["product.template"].create(
            {
                "name": "Variant Only Intermediate",
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
        int_red = int_tmpl.product_variant_ids.filtered(
            lambda p: (
                color_red
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )

        # Variant-specific BoM only (product_id set) pointing to anchor
        self.env["mrp.bom"].create(
            {
                "product_id": int_red.id,
                "product_tmpl_id": int_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {"product_id": self.bulk_material.id, "product_qty": 1.0},
                    ),
                ],
            }
        )

        campaign = self.create_campaign(self.bulk_material)
        line = self.create_line(int_red, campaign)
        line._construct_downstream_tree_line()

        # Variant-only BoM must be found: intermediate + anchor = 2 lines
        self.assertEqual(len(campaign.line_ids), 2)
        anchor_line = campaign.line_ids.filtered_domain(
            [("product_id", "=", self.bulk_material.id)]
        )
        self.assertEqual(len(anchor_line), 1)
        self.assertEqual(line.downstream_line_id, anchor_line)

    def test_anchor_product_computed_with_variant_bom(self) -> None:
        """anchor_product_id must be invalidated when variant_bom_ids change."""
        color_attr = self.env["product.attribute"].create({"name": "Color"})
        color_red = self.env["product.attribute.value"].create(
            {"name": "Red", "attribute_id": color_attr.id}
        )
        color_blue = self.env["product.attribute.value"].create(
            {"name": "Blue", "attribute_id": color_attr.id}
        )

        # End product with variants but NO BoM yet
        end_tmpl = self.env["product.template"].create(
            {
                "name": "Variant Anchor Test",
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

        # No BoM -> no anchor
        self.assertFalse(variant_red.anchor_product_id)

        # Add variant-specific BoM with bom_line pointing to anchor
        self.env["mrp.bom"].create(
            {
                "product_id": variant_red.id,
                "product_tmpl_id": end_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {"product_id": self.bulk_material.id, "product_qty": 1.0},
                    ),
                ],
            }
        )

        # anchor_product_id must be recomputed (variant_bom_ids in depends)
        self.assertEqual(variant_red.anchor_product_id, self.bulk_material)
