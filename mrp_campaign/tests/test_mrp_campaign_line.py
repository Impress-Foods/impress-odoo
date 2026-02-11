from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestMrpCampaignLine(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create a product category
        cls.product_category = cls.env["product.category"].create(
            {
                "name": "Test Category",
            }
        )

        # Create a test product
        cls.product_tmpl = cls.env["product.template"].create(
            {
                "name": "Test Product Template",
                "type": "product",
                "categ_id": cls.product_category.id,
                "mrp_max_batch_size": 0,  # Default to non-batch
            }
        )
        cls.product = cls.product_tmpl.product_variant_id

        # Create a Bill of Materials (BoM) for the product
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.product_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
            }
        )

        # Create a campaign
        cls.campaign = cls.env["mrp.campaign"].create(
            {
                "name": "Test Campaign",
                "product_id": cls.product.id,
            }
        )

    def _create_campaign_line(self, product, bom, qty=0.0):
        return self.env["mrp.campaign.line"].create(
            {
                "campaign_id": self.campaign.id,
                "product_id": product.id,
                "bom_id": bom.id,
                "qty": qty,
            }
        )

    def _assert_mos_quantities(self, line, expected_quantities):
        """Helper to assert the quantities of MOs linked to a campaign line."""
        mo_quantities = sorted(line.production_ids.mapped("product_qty"))
        self.assertEqual(
            mo_quantities,
            sorted(expected_quantities),
            (
                f"Expected MO quantities: {sorted(expected_quantities)},"
                f"Got: {mo_quantities}"
            ),
        )
        self.assertEqual(
            len(line.production_ids),
            len(expected_quantities),
            f"Expected {len(expected_quantities)} MOs, Got {len(line.production_ids)}",
        )

    def _create_mo_with_state(self, line, qty, state="draft"):
        """Helper to create an MO with a specific state."""
        mo = self.env["mrp.production"].create(
            {
                "product_id": line.product_id.id,
                "bom_id": line.bom_id.id,
                "product_qty": qty,
                "campaign_line_id": line.id,
                "created_by_campaign": True,
            }
        )
        if state != "draft":
            mo.write({"state": state})
        return mo

    # --- Batch Produced Product Tests ---

    def test_batch_initial_creation(self):
        """Test initial MO creation for a batch-produced product."""
        self.product_tmpl.mrp_max_batch_size = 10

        line = self._create_campaign_line(self.product, self.bom)
        line.productions_created = True  # Simulate that _compute_qty has run

        line._adjust_mos(25.0)
        self._assert_mos_quantities(line, [10.0, 10.0, 5.0])

    def test_batch_initial_creation_exact_batch(self):
        """Test initial MO creation with quantity exact multiple of batch size."""
        self.product_tmpl.mrp_max_batch_size = 10

        line = self._create_campaign_line(self.product, self.bom)
        line.productions_created = True

        line._adjust_mos(20.0)
        self._assert_mos_quantities(line, [10.0, 10.0])

    def test_batch_increasing_quantity(self):
        """Test increasing quantity for a batch-produced
        product by updating existing MOs."""
        self.product_tmpl.mrp_max_batch_size = 10

        line = self._create_campaign_line(self.product, self.bom)
        line.productions_created = True

        # Manually create initial MOs for a total of 25.0 (2x10, 1x5)
        mo1 = self._create_mo_with_state(line, 10.0, "draft")
        mo2 = self._create_mo_with_state(line, 10.0, "draft")
        mo3 = self._create_mo_with_state(line, 5.0, "draft")
        initial_mo_ids = set(line.production_ids.ids)

        self._assert_mos_quantities(line, [10.0, 10.0, 5.0])

        # Increase quantity to 35.0: expect 3x10, 1x5.
        # This means one of the existing MOs should be updated, and one new MO created.
        line._adjust_mos(35.0)
        self._assert_mos_quantities(line, [10.0, 10.0, 10.0, 5.0])

        # Verify that at least some original MOs were kept and updated,
        #   not all deleted and recreated
        final_mo_ids = set(line.production_ids.ids)

        # At least the number of initial MOs - (if any were deleted) should be present
        # In this specific case, no MOs should be deleted,
        #   one should be updated, and one new created.
        # It's difficult to assert exact MO IDs without
        #   making assumptions about matching logic,
        # but we can assert that at least some original MOs persisted.
        self.assertGreaterEqual(
            len(initial_mo_ids.intersection(final_mo_ids)),
            2,
            "Expected at least 2 original MOs to persist after increasing quantity.",
        )

        # Re-fetch MOs to get updated quantities
        _updated_mo1 = mo1.browse(mo1.id)
        _updated_mo2 = mo2.browse(mo2.id)
        _updated_mo3 = mo3.browse(mo3.id)

        # Check if the MOs' quantities were updated correctly
        # This part is complex because the greedy matching might update any MO.
        # The easiest is to ensure that the sum of quantities is
        #   correct and the number of MOs is correct.
        # For a truly robust test, we would need to mock the wizard or trace MOs
        #   by ID and their expected roles.
        # Given the greedy matching, MO3 (5.0) might become 10.0,
        #   and a new 5.0 MO might be created.
        # Or mo1(10.0) and mo2(10.0) kept, mo3(5.0) becomes 10.0 and a new 5.0 created.
        # The best we can do is ensure the overall count and sum are correct,
        #   and some MOs persisted.
        # The greedy matching strategy will decide which exact MO gets
        #   which target quantity.
        # For this test, we just ensure the count and sum are right,
        #   and not all MOs were deleted.
        self.assertEqual(sum(line.production_ids.mapped("product_qty")), 35.0)
        self.assertEqual(len(line.production_ids), 4)

    def test_batch_decreasing_quantity(self):
        """Test decreasing quantity for a batch-produced product
        by updating and deleting MOs."""
        self.product_tmpl.mrp_max_batch_size = 10

        line = self._create_campaign_line(self.product, self.bom)
        line.productions_created = True

        # Manually create initial MOs for a total of 35.0 (3x10, 1x5)
        mo_a = self._create_mo_with_state(line, 10.0, "draft")
        mo_b = self._create_mo_with_state(line, 10.0, "draft")
        mo_c = self._create_mo_with_state(line, 10.0, "draft")
        mo_d = self._create_mo_with_state(line, 5.0, "draft")
        initial_mo_ids = set(line.production_ids.ids)

        self._assert_mos_quantities(line, [10.0, 10.0, 10.0, 5.0])

        # Decrease quantity to 15.0: expect 1x10, 1x5.
        # This means two MOs should be deleted, and two should be kept/updated.
        line._adjust_mos(15.0)
        self._assert_mos_quantities(line, [10.0, 5.0])

        # Verify that some original MOs were kept and updated
        final_mo_ids = set(line.production_ids.ids)
        self.assertGreaterEqual(
            len(initial_mo_ids.intersection(final_mo_ids)),
            2,
            "Expected at least 2 original MOs to persist after decreasing quantity.",
        )

        # Re-fetch MOs to get updated quantities
        _updated_mo_a = mo_a.browse(mo_a.id)
        _updated_mo_b = mo_b.browse(mo_b.id)
        _updated_mo_c = mo_c.browse(mo_c.id)
        _updated_mo_d = mo_d.browse(mo_d.id)

        # In a greedy match, it's likely two of the 10.0 MOs were deleted, .
        #   and one 10.0 and one 5.0 remain.
        # Ensure the overall count and sum are right, and some MOs persisted.
        self.assertEqual(sum(line.production_ids.mapped("product_qty")), 15.0)
        self.assertEqual(len(line.production_ids), 2)

    def test_batch_decrease_to_zero(self):
        """Test decreasing quantity to zero for a batch-produced product."""
        self.product_tmpl.mrp_max_batch_size = 10

        line = self._create_campaign_line(self.product, self.bom)
        line.productions_created = True

        line._adjust_mos(15.0)  # Initial: 1x10, 1x5
        self._assert_mos_quantities(line, [10.0, 5.0])

        line._adjust_mos(0.0)  # Decrease to zero
        self._assert_mos_quantities(line, [])

    def test_batch_decrease_below_fixed_mos(self):
        """Test decreasing quantity below fixed (done) MOs for batch-produced."""
        self.product_tmpl.mrp_max_batch_size = 10

        line = self._create_campaign_line(self.product, self.bom)
        line.productions_created = True

        # Create a fixed MO (state 'done')
        self._create_mo_with_state(line, 10.0, "done")

        # Attempt to adjust to a quantity less than the fixed MO
        with self.assertRaises(ValidationError):
            line._adjust_mos(5.0)

        # Ensure the fixed MO is still there and no new MOs were created
        self._assert_mos_quantities(line, [10.0])  # Only the fixed MO

    # --- Non-Batch Produced Product Tests ---

    def test_non_batch_initial_creation(self):
        """Test initial MO creation for a non-batch-produced product."""
        self.product_tmpl.mrp_max_batch_size = 0  # Ensure non-batch

        line = self._create_campaign_line(self.product, self.bom)
        line.productions_created = True

        line._adjust_mos(15.0)
        self._assert_mos_quantities(line, [15.0])

    def test_non_batch_updating_quantity(self):
        """Test updating quantity for a non-batch-produced product."""
        self.product_tmpl.mrp_max_batch_size = 0

        line = self._create_campaign_line(self.product, self.bom)
        line.productions_created = True

        line._adjust_mos(15.0)  # Initial: 1x15
        self._assert_mos_quantities(line, [15.0])

        line._adjust_mos(25.0)  # Update to 1x25
        self._assert_mos_quantities(line, [25.0])

    def test_non_batch_decrease_to_zero(self):
        """Test decreasing quantity to zero for a non-batch-produced product."""
        self.product_tmpl.mrp_max_batch_size = 0

        line = self._create_campaign_line(self.product, self.bom)
        line.productions_created = True

        line._adjust_mos(25.0)  # Initial: 1x25
        self._assert_mos_quantities(line, [25.0])

        line._adjust_mos(0.0)  # Decrease to zero
        self._assert_mos_quantities(line, [])

    def test_non_batch_decrease_below_fixed_mos(self):
        """Test decreasing quantity below fixed (done) MOs for non-batch-produced."""
        self.product_tmpl.mrp_max_batch_size = 0

        line = self._create_campaign_line(self.product, self.bom)
        line.productions_created = True

        # Create a fixed MO (state 'done')
        self._create_mo_with_state(line, 10.0, "done")

        # Attempt to adjust to a quantity less than the fixed MO
        with self.assertRaises(ValidationError):
            line._adjust_mos(5.0)

        # Ensure the fixed MO is still there and no new MOs were created
        self._assert_mos_quantities(line, [10.0])  # Only the fixed MO

    def test_non_batch_multiple_adjustable_mos_error(self):
        """
        Test that non-batch produced lines raise ValidationError
        if multiple adjustable MOs exist.
        This tests the explicit validation in _adjust_mos,
        not a state reachable through normal _adjust_mos calls.
        """
        self.product_tmpl.mrp_max_batch_size = 0

        line = self._create_campaign_line(self.product, self.bom)
        line.productions_created = True

        # Manually create two adjustable MOs for a non-batch product
        self._create_mo_with_state(line, 10.0, "draft")
        self._create_mo_with_state(line, 5.0, "confirmed")

        # Now call _adjust_mos, which should catch this invalid state
        with self.assertRaises(ValidationError):
            line._adjust_mos(15.0)  # Any non-zero quantity will trigger the check
