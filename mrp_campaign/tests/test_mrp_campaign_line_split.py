import logging

from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare

from .test_common import CampaignCase

_logger = logging.getLogger(__name__)


class TestMrpCampaignLineAdjust(CampaignCase):
    def test_adjust_mos_basic_non_batch_increase(self):
        # Scenario: Non-batch product, increase quantity, no fixed MOs
        # Expect: One MO updated to new quantity

        INITIAL_QTY = 50.0
        NEW_QTY = 75.0

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = 0

        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        line.qty = INITIAL_QTY

        line.make_production_order()

        self.assertEqual(len(line.production_ids), 1)
        self.assertEqual(line.production_ids.product_qty, INITIAL_QTY)

        line._adjust_mos(NEW_QTY)

        self.assertEqual(len(line.production_ids), 1)
        updated_mo = line.production_ids[0]
        self.assertEqual(updated_mo.product_qty, NEW_QTY)
        self.assertEqual(
            float_compare(updated_mo.product_qty, NEW_QTY, precision_digits=2), 0
        )

    def test_adjust_mos_basic_non_batch_decrease(self):
        # Scenario: Non-batch product, decrease quantity, no fixed MOs
        # Expect: One MO updated to new quantity
        INITIAL_QTY = 75.0
        NEW_QTY = 50.0

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = 0

        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        line.qty = INITIAL_QTY

        line.make_production_order()

        self.assertEqual(len(line.production_ids), 1)
        self.assertEqual(line.production_ids.product_qty, INITIAL_QTY)

        line._adjust_mos(NEW_QTY)

        self.assertEqual(len(line.production_ids), 1)
        updated_mo = line.production_ids[0]
        self.assertEqual(updated_mo.product_qty, NEW_QTY)
        self.assertEqual(
            float_compare(updated_mo.product_qty, NEW_QTY, precision_digits=2), 0
        )

    def test_adjust_mos_non_batch_no_change(self):
        # Scenario: Non-batch product, quantity no change, no fixed MOs
        # Expect: MO quantity remains same
        INITIAL_QTY = 50.0
        NEW_QTY = 50.0  # Same quantity

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = 0

        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        line.qty = INITIAL_QTY

        line.make_production_order()

        self.assertEqual(len(line.production_ids), 1)
        self.assertEqual(line.production_ids.product_qty, INITIAL_QTY)

        line._adjust_mos(NEW_QTY)

        self.assertEqual(len(line.production_ids), 1)
        updated_mo = line.production_ids[0]
        self.assertEqual(updated_mo.product_qty, INITIAL_QTY)
        self.assertEqual(
            float_compare(updated_mo.product_qty, INITIAL_QTY, precision_digits=2), 0
        )

    def test_adjust_mos_non_batch_zero_new_quantity(self):
        # Scenario: Non-batch product, new quantity is zero
        # Expect: Existing MO unlinked
        INITIAL_QTY = 50.0
        NEW_QTY = 0.0

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = 0

        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        line.qty = INITIAL_QTY

        line.make_production_order()

        self.assertEqual(len(line.production_ids), 1)
        self.assertEqual(line.production_ids.product_qty, INITIAL_QTY)

        line._adjust_mos(NEW_QTY)

        self.assertEqual(len(line.production_ids), 0)

    def test_adjust_mos_non_batch_initial_creation(self):
        NEW_QTY = 60.0

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = 0

        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        line.productions_created = True

        self.assertEqual(len(line.production_ids), 0)

        line._adjust_mos(NEW_QTY)

        self.assertEqual(len(line.production_ids), 1)
        new_mo = line.production_ids[0]
        self.assertEqual(new_mo.product_qty, NEW_QTY)
        self.assertEqual(
            float_compare(new_mo.product_qty, NEW_QTY, precision_digits=2), 0
        )

    def test_adjust_mos_non_batch_multiple_mos_raises_error(self):
        NEW_QTY = 100.0  # Arbitrary new quantity, should not matter for the error

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = 0

        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        line.qty = 50.0

        # Create two initial MOs linked to the campaign line
        self.env["mrp.production"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "product_uom_id": self.int_prod_x_red.uom_id.id,
                "bom_id": self.bom_int_prod_x.id,
                "product_qty": 25.0,
                "campaign_line_id": line.id,
                "created_by_campaign": True,
            }
        )
        self.env["mrp.production"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "product_uom_id": self.int_prod_x_red.uom_id.id,
                "bom_id": self.bom_int_prod_x.id,
                "product_qty": 25.0,
                "campaign_line_id": line.id,
                "created_by_campaign": True,
            }
        )
        line.productions_created = True

        self.assertEqual(len(line.production_ids), 2)

        expected_error_message = (
            "Non-batch produced line should only have one Manufacturing Order."
        )

        with self.assertRaisesRegex(ValidationError, expected_error_message):
            line._adjust_mos(NEW_QTY)

    def test_adjust_mos_non_batch_fixed_mos_increase(self):
        # Scenario: Non-batch product, increase quantity, with fixed MOs
        # Expect: Adjustable MO updated to cover difference
        FIXED_QTY = 20.0
        ADJUSTABLE_QTY = 30.0
        INITIAL_QTY = FIXED_QTY + ADJUSTABLE_QTY
        NEW_QTY = 80.0

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = 0

        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        line.qty = INITIAL_QTY

        # Manually create MOs to allow for 2 MOs on non-batch
        # Create a fixed MO (done)
        fixed_mo = self.env["mrp.production"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "bom_id": self.bom_int_prod_x.id,
                "product_uom_id": self.int_prod_x_red.uom_id.id,
                "product_qty": FIXED_QTY,
                "campaign_line_id": line.id,
                "created_by_campaign": True,
                "state": "done",
            }
        )
        # Create an adjustable MO (confirmed)
        adjustable_mo = self.env["mrp.production"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "bom_id": self.bom_int_prod_x.id,
                "product_uom_id": self.int_prod_x_red.uom_id.id,
                "product_qty": ADJUSTABLE_QTY,
                "campaign_line_id": line.id,
                "created_by_campaign": True,
                "state": "confirmed",
            }
        )
        line.productions_created = True

        self.assertEqual(len(line.production_ids), 2)

        line._adjust_mos(NEW_QTY)

        self.assertEqual(len(line.production_ids), 2)
        # Fixed MO should be untouched
        self.assertEqual(fixed_mo.product_qty, FIXED_QTY)
        # Adjustable MO should be updated
        self.assertEqual(adjustable_mo.product_qty, NEW_QTY - FIXED_QTY)

    def test_adjust_mos_non_batch_fixed_mos_decrease_raises_error(self):
        # Scenario: Non-batch product, decrease quantity below fixed production
        # Expect: ValidationError
        INITIAL_QTY = 50.0
        NEW_QTY = 40.0

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = 0

        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        line.qty = INITIAL_QTY

        mo = line.make_production_order()
        mo.action_confirm()

        self.assertEqual(mo.product_qty, INITIAL_QTY)
        mo.qty_producing = mo.product_qty
        mo.button_mark_done()

        expected_error_message = (
            "Cannot adjust to a quantity less than what has already "
        )

        with self.assertRaisesRegex(ValidationError, expected_error_message):
            line._adjust_mos(NEW_QTY)

    def test_adjust_batch_mos_increase_target_quantities(self):
        # Scenario: Batch product, increase total quantity from existing MOs
        # Expect: MOs are updated and new ones created to match new target
        BATCH_SIZE = 100.0
        INITIAL_QTY = 150.0  # One batch of 100, one of 50
        NEW_QTY = (
            INITIAL_QTY + BATCH_SIZE
        )  # Should become two batches of 100, one of 50

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = BATCH_SIZE

        campaign = self.create_campaign(self.int_prod_x_red)

        line = self.create_line(self.int_prod_x_red, campaign)
        self.assertEqual(line.batch_size, BATCH_SIZE)

        line.qty = INITIAL_QTY

        mos = line.make_production_order()

        # Verify the pre-change state is as expected
        self.assertEqual(len(line.production_ids), 2)
        self.assertCountEqual([BATCH_SIZE, 50.0], mos.mapped("product_qty"))

        line._adjust_mos(NEW_QTY)

        self.assertEqual(len(line.production_ids), 3)
        self.assertCountEqual(
            line.production_ids.mapped("product_qty"), [BATCH_SIZE, BATCH_SIZE, 50.0]
        )

    def test_adjust_batch_mos_decrease_target_quantities(self):
        # Scenario: Batch product, decrease total quantity
        # Expect: Fewer MOs or MOs adjusted, excess unlinked
        BATCH_SIZE = 100.0
        INITIAL_QTY = 250.0  # Two batches of 100, one of 50
        NEW_QTY = 150.0  # Should become one batch of 100, one of 50

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = BATCH_SIZE

        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        self.assertEqual(line.batch_size, BATCH_SIZE)

        line.qty = INITIAL_QTY
        mos = line.make_production_order()

        self.assertEqual(len(line.production_ids), 3)
        self.assertCountEqual(mos.mapped("product_qty"), [BATCH_SIZE, BATCH_SIZE, 50.0])

        line._adjust_mos(NEW_QTY)

        self.assertEqual(
            len(line.production_ids), 2, line.production_ids.mapped("product_qty")
        )
        self.assertCountEqual(
            line.production_ids.mapped("product_qty"), [BATCH_SIZE, 50.0]
        )

    def test_adjust_batch_mos_no_change(self):
        # Scenario: Batch product, total quantity unchanged
        # Expect: MOs remain as is
        BATCH_SIZE = 100.0
        INITIAL_QTY = 150.0
        NEW_QTY = 150.0

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = BATCH_SIZE

        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        self.assertEqual(line.batch_size, BATCH_SIZE)

        line.qty = INITIAL_QTY

        self.env["mrp.production"].create(
            [
                {
                    "product_id": self.int_prod_x_red.id,
                    "product_uom_id": self.int_prod_x_red.uom_id.id,
                    "bom_id": self.bom_int_prod_x.id,
                    "product_qty": 100.0,
                    "campaign_line_id": line.id,
                },
                {
                    "product_id": self.int_prod_x_red.id,
                    "product_uom_id": self.int_prod_x_red.uom_id.id,
                    "bom_id": self.bom_int_prod_x.id,
                    "product_qty": 50.0,
                    "campaign_line_id": line.id,
                },
            ]
        )
        line.productions_created = True
        self.assertEqual(len(line.production_ids), 2)

        line._adjust_mos(NEW_QTY)

        self.assertEqual(len(line.production_ids), 2)
        self.assertCountEqual(
            line.production_ids.mapped("product_qty"), [BATCH_SIZE, 50.0]
        )

    def test_adjust_batch_mos_mixed_fixed_and_adjustable(self):
        # Scenario: Batch product, some fixed MOs, others adjustable
        # Expect: Adjustable MOs handle the remaining quantity
        BATCH_SIZE = 100.0
        FIXED_QTY = 100.0  # One full batch, 'done'
        ADJUSTABLE_QTY = 150.0  # One full, one partial
        INITIAL_QTY = FIXED_QTY + ADJUSTABLE_QTY  # 250.0
        NEW_QTY = 320.0  # Fixed (100) + required (220)

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = BATCH_SIZE
        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        self.assertEqual(line.batch_size, BATCH_SIZE)

        line.qty = INITIAL_QTY

        # Create fixed MO
        self.env["mrp.production"].create(
            {
                "product_id": self.int_prod_x_red.id,
                "product_uom_id": self.int_prod_x_red.uom_id.id,
                "bom_id": self.bom_int_prod_x.id,
                "product_qty": FIXED_QTY,
                "campaign_line_id": line.id,
                "state": "done",
            }
        )
        # Create adjustable MOs
        self.env["mrp.production"].create(
            [
                {
                    "product_id": self.int_prod_x_red.id,
                    "product_uom_id": self.int_prod_x_red.uom_id.id,
                    "bom_id": self.bom_int_prod_x.id,
                    "product_qty": 100.0,
                    "campaign_line_id": line.id,
                },
                {
                    "product_id": self.int_prod_x_red.id,
                    "product_uom_id": self.int_prod_x_red.uom_id.id,
                    "bom_id": self.bom_int_prod_x.id,
                    "product_qty": 50.0,
                    "campaign_line_id": line.id,
                },
            ]
        )
        line.productions_created = True
        self.assertEqual(len(line.production_ids), 3)

        line._adjust_mos(NEW_QTY)

        # Total MOs = 1 fixed + 3 adjustable (100, 100, 20)
        self.assertEqual(len(line.production_ids), 4)

        fixed_mo = line.production_ids.filtered(lambda mo: mo.state == "done")
        self.assertEqual(fixed_mo.product_qty, BATCH_SIZE)

        adjustable_mos = line.production_ids.filtered(lambda mo: mo.state != "done")
        # Required from adjustable is 220 -> 100, 100, 20
        self.assertCountEqual(
            adjustable_mos.mapped("product_qty"), [BATCH_SIZE, BATCH_SIZE, 20.0]
        )

    def test_adjust_batch_mos_all_fixed_decrease_raises_error(self):
        # Scenario: Batch product, all MOs fixed, new quantity less than fixed
        # Expect: ValidationError
        BATCH_SIZE = 100
        FIXED_QTY_1 = 100.0
        FIXED_QTY_2 = 50.0
        INITIAL_QTY = FIXED_QTY_1 + FIXED_QTY_2  # 150.0
        NEW_QTY = 100.0  # Less than total fixed quantity

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = BATCH_SIZE
        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        self.assertEqual(line.batch_size, BATCH_SIZE)

        line.qty = INITIAL_QTY

        self.env["mrp.production"].create(
            [
                {
                    "product_id": self.int_prod_x_red.id,
                    "product_uom_id": self.int_prod_x_red.uom_id.id,
                    "bom_id": self.bom_int_prod_x.id,
                    "product_qty": FIXED_QTY_1,
                    "campaign_line_id": line.id,
                    "state": "done",
                },
                {
                    "product_id": self.int_prod_x_red.id,
                    "product_uom_id": self.int_prod_x_red.uom_id.id,
                    "bom_id": self.bom_int_prod_x.id,
                    "product_qty": FIXED_QTY_2,
                    "campaign_line_id": line.id,
                    "state": "to_close",
                },
                {
                    "product_id": self.int_prod_x_red.id,
                    "product_uom_id": self.int_prod_x_red.uom_id.id,
                    "bom_id": self.bom_int_prod_x.id,
                    "product_qty": FIXED_QTY_2,
                    "campaign_line_id": line.id,
                    "state": "cancel",
                },
            ]
        )
        line.productions_created = True

        expected_error_message = (
            "Cannot adjust to a quantity less than what has already "
        )
        with self.assertRaisesRegex(ValidationError, expected_error_message):
            line._adjust_mos(NEW_QTY)

    def test_adjust_batch_mos_target_creation(self):
        # Scenario: Batch product, no existing adjustable MOs, new ones created
        # Expect: New MOs created to meet target quantities
        BATCH_SIZE = 100.0
        INITIAL_QTY = 0
        NEW_QTY = 250.0  # Should create two batches of 100, one of 50

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = BATCH_SIZE
        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        line.qty = INITIAL_QTY

        self.assertEqual(line.batch_size, BATCH_SIZE)

        line.productions_created = True
        self.assertEqual(len(line.production_ids), 0)

        line._adjust_mos(NEW_QTY)

        self.assertEqual(len(line.production_ids), 3)
        self.assertCountEqual(
            line.production_ids.mapped("product_qty"), [100.0, 100.0, 50.0]
        )

    def test_adjust_batch_mos_excess_deletion(self):
        # Scenario: Batch product, too many MOs, some need to be deleted
        # Expect: Excess MOs unlinked
        BATCH_SIZE = 100.0
        INITIAL_QTY = 250.0  # Two batches of 100, one of 50
        NEW_QTY = 80.0  # Should become one batch of 80

        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = BATCH_SIZE
        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        self.assertEqual(line.batch_size, BATCH_SIZE)

        line.qty = INITIAL_QTY

        line.make_production_order()
        self.assertEqual(len(line.production_ids), 3)

        line._adjust_mos(NEW_QTY)

        self.assertEqual(len(line.production_ids), 1)
        self.assertEqual(line.production_ids.product_qty, NEW_QTY)

    def test_adjust_batch_mos_required_adjustable_zero(self):
        # Scenario: Batch product, new_quantity equals fixed_qty_produced,
        # resulting in required_from_adjustable_mos == 0.
        # Expect: All adjustable MOs are unlinked.
        BATCH_SIZE = 100.0
        FIXED_QTY = 100.0
        ADJUSTABLE_QTY = 50.0  # This MO should be unlinked
        self.int_prod_x_red.product_tmpl_id.mrp_max_batch_size = BATCH_SIZE

        campaign = self.create_campaign(self.int_prod_x_red)
        line = self.create_line(self.int_prod_x_red, campaign)
        self.assertEqual(line.batch_size, BATCH_SIZE)

        line.qty = FIXED_QTY + ADJUSTABLE_QTY  # Initial total qty
        mos = line.make_production_order()
        mos.action_confirm()

        self.assertEqual(len(line.production_ids), 2)
        self.assertCountEqual(mos.mapped("product_qty"), [BATCH_SIZE, ADJUSTABLE_QTY])
        fixed_mo = mos.filtered(lambda prod: prod.product_qty == BATCH_SIZE)
        adjustable_mo = mos - fixed_mo

        fixed_mo.qty_producing = FIXED_QTY
        fixed_mo.button_mark_done()

        self.assertIn(fixed_mo, line.production_ids)
        self.assertIn(adjustable_mo, line.production_ids)

        # Set the total qty to the fixed qty
        line._adjust_mos(FIXED_QTY)

        # Only the fixed MO should remain
        self.assertEqual(len(line.production_ids), 1)
        self.assertIn(fixed_mo, line.production_ids)
        self.assertEqual(fixed_mo.product_qty, FIXED_QTY)
        self.assertNotIn(adjustable_mo, line.production_ids)
