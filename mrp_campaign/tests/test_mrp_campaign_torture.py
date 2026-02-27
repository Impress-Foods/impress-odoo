import json
import logging

from odoo.tools import float_compare

from .test_common import CampaignCase

_logger = logging.getLogger(__name__)


class TestMrpCampaignTorture(CampaignCase):
    def test_campaign_partition_torture_scenario(self):
        """
        Flow: End Product (Demand) -> Sub-Assembly ->
            Component -> Bulk Material (Anchor)
        Rules tested:
        1. Cascading demand from end product down to anchor.
        2. Buffer application at the Anchor level (must define batch/buffer on anchor).
        3. Protection against splitting below committed quantities.
        4. Matching logic for "ugly" non-integer splits.
        """
        # --- 1. Setup Hierarchy (Anchor at the Bottom) ---

        # Level 4: Bulk Material (Anchor, BATCH: 10, BUFFER: 10%)
        # Note: Must have a BoM to be included in the tree by current logic.
        bulk_material = self.env["product.product"].create(
            {
                "name": "Torture Bulk Anchor",
                "type": "product",
                "mrp_max_batch_size": 10.0,
                "campaign_buffer_percent": 0.10,
            }
        )
        bulk_material.product_tmpl_id.is_campaign_anchor = True
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": bulk_material.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
                # Components of anchor are ignored by campaign tree
            }
        )

        # Level 3: Component (Standard)
        component = self.env["product.product"].create(
            {
                "name": "Torture Component",
                "type": "product",
            }
        )
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": component.product_tmpl_id.id,
                "product_qty": 1.0,
                "bom_line_ids": [
                    (0, 0, {"product_id": bulk_material.id, "product_qty": 1.0})
                ],
            }
        )

        # Level 2: Sub-Assembly (Standard)
        sub_assembly = self.env["product.product"].create(
            {
                "name": "Torture Sub-Assembly",
                "type": "product",
            }
        )
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": sub_assembly.product_tmpl_id.id,
                "product_qty": 1.0,
                "bom_line_ids": [
                    (0, 0, {"product_id": component.id, "product_qty": 2.0})
                ],
            }
        )

        # Level 1: End Product (Demand starts here)
        end_product = self.env["product.product"].create(
            {
                "name": "Torture End Product",
                "type": "product",
            }
        )
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": end_product.product_tmpl_id.id,
                "product_qty": 1.0,
                "bom_line_ids": [
                    (0, 0, {"product_id": sub_assembly.id, "product_qty": 1.0})
                ],
            }
        )

        self.env.flush_all()

        # --- 2. Initial Campaign and Demand ---
        # Demand for 25 units of End Product
        campaign = self.create_campaign(bulk_material)
        self.create_demand(end_product, qty=25.0, campaign=campaign)
        campaign.action_plan()

        # Verify initial tree states
        # Demand 25 -> Sub 25 -> Comp 50 -> Bulk 50
        # Bulk is Anchor with 10% buffer -> Bulk Qty: 50 + 10% = 55.0
        lines = campaign.line_ids
        bulk_line = lines.filtered(lambda line: line.product_id == bulk_material)

        def assert_qty(val1, val2, msg=""):
            self.assertEqual(
                float_compare(val1, val2, precision_rounding=0.001),
                0,
                f"{msg}: {val1} != {val2}",
            )

        assert_qty(bulk_line.qty, 55.0, "Anchor should have 10% buffer")
        self.assertEqual(
            len(bulk_line.production_ids), 6, "Batches of 10, 10, 10, 10, 10, 5"
        )

        # --- 3. Torture: Fix some MOs ---
        # Fix one 10-unit MO at the anchor level
        bulk_mos = bulk_line.production_ids.sorted("product_qty", reverse=True)
        bulk_mos[0].action_confirm()
        bulk_mos[0].write({"state": "progress"})  # Qty 10 is FIXED

        # --- 4. The Torturous Partition ---
        # Split demand: 14.5 units of End Product stay in A.
        # A: End 14.5 -> Sub 14.5 -> Comp 29.0 -> Bulk 29.0 + 10% = 31.9

        wizard = (
            self.env["mrp.campaign.partition.wizard"]
            .with_context(
                **{
                    "active_id": campaign.id,
                    "active_model": "mrp.campaign",
                    "default_partition_mode": "split",
                }
            )
            .create({})
        )

        data = json.loads(wizard.partition_data_json)
        data["demand_moves"][0]["fulfilled_qty"] = 14.5

        def update_node(node, planned_qty):
            line_id = node["line_id"]
            line_rec = self.env["mrp.campaign.line"].browse(line_id)
            node["quantities"]["planned"] = planned_qty
            buffer = (
                (1 + line_rec.buffer_percent) if line_rec.is_batch_produced else 1.0
            )
            qty_for_children = planned_qty * buffer
            for branch in node["upstream_branches"]:
                child_line = self.env["mrp.campaign.line"].browse(branch["line_id"])
                factor = line_rec.bom_id.bom_line_ids.filtered(
                    lambda line, cl=child_line: line.product_id == cl.product_id
                ).product_qty
                update_node(branch, qty_for_children * factor)

        update_node(data["tree"], 14.5)
        wizard.partition_data_json = json.dumps(data)
        wizard.action_partition_campaign()

        # --- 5. Verifications ---
        campaign_b = self.env["mrp.campaign"].search(
            [("bo_source_id", "=", campaign.id)], limit=1
        )
        self.assertTrue(campaign_b)

        # Verify Campaign A Anchor (Total req: 31.9)
        # One fixed at 10. Remaining adjustable req: 21.9.
        # Adjustable MOs should be [10, 10, 1.9]
        assert_qty(bulk_line.qty, 31.9)
        bulk_mos_a = bulk_line.production_ids.filtered(lambda m: m.state != "cancel")
        self.assertEqual(
            len(bulk_mos_a), 4, "One fixed 10, two resized 10s, one resized 1.9"
        )
        assert_qty(sum(bulk_mos_a.mapped("product_qty")), 31.9)

        # Verify Campaign B Anchor (End 10.5 -> Comp 21 -> Bulk 21 + 10% = 23.1)
        line_b_bulk = campaign_b.line_ids.filtered(
            lambda line: line.product_id == bulk_material
        )
        assert_qty(line_b_bulk.qty, 23.1)
        bulk_mos_b = line_b_bulk.production_ids.filtered(lambda m: m.state != "cancel")
        self.assertEqual(len(bulk_mos_b), 3, "10, 10, 3.1")
        assert_qty(sum(bulk_mos_b.mapped("product_qty")), 23.1)
