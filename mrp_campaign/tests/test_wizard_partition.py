import logging

from odoo.exceptions import ValidationError

from .test_common import CampaignCase

_logger = logging.getLogger(__name__)


class TestMrpCampaignPartitionWizard(CampaignCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wizard = cls.env["mrp.campaign.partition.wizard"]

    @classmethod
    def create_full_campaign(cls, product, qty):
        campaign = cls.create_campaign(cls.bulk_material)
        demand = cls.create_demand(product, 100, campaign)
        return campaign, demand

    # --- JSON Generation & Structure ---

    def test_make_partition_json_structure(self):
        """Verify the wizard generates a correctly structured JSON
        with 'meta', 'tree', and 'demand_moves'."""
        campaign = self.create_campaign(self.bulk_material)
        demand = self.create_demand(self.int_prod_x_blue, 100, campaign)
        campaign.action_plan()
        data = self.wizard._make_partition_json(campaign)

        self.assertTrue(data.get("meta", False))
        self.assertEqual(data["meta"].get("campaign_id", False), campaign.id)
        self.assertTrue(data.get("tree", False))
        self.assertTrue(data.get("demand_moves", False))
        self.assertEqual(
            data["demand_moves"][0].get("proxy_id", False),
            demand.demand_proxy_ids[0].id,
        )

    def test_make_partition_json_structure_no_root(self):
        """Verify the wizard generates a correctly structured JSON
        with 'meta', 'tree', and 'demand_moves'."""
        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.int_prod_x_blue, 100, campaign)
        with self.assertRaises(ValidationError):
            self.wizard._make_partition_json(campaign)

    def test_make_partition_json_structure_multiple_roots(self):
        """Verify the wizard generates a correctly structured JSON
        with 'meta', 'tree', and 'demand_moves'."""
        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(self.int_prod_x_blue, 100, campaign)
        campaign.action_plan()
        self.create_line(self.bulk_material, campaign)

        with self.assertRaises(ValidationError):
            self.wizard._make_partition_json(campaign)

    def test_recursive_tree_quantities(self):
        """Verify that _build_tree_recursive correctly calculates
        planned, done, and wip quantities for a line."""
        QTY = 100.0
        FACTOR = 3.0  # Factor between int_prod and bulk_material

        campaign = self.create_campaign(self.bulk_material)
        self.create_demand(
            self.int_prod_y_red,
            QTY,
            campaign,
        )

        campaign.action_plan()
        tree = self.wizard._make_partition_json(campaign)["tree"]

        # Check for all baseline values (nothing is done in the campaign yet)
        self.assertTrue(
            all([value == 0 for value in self.get_all_values_for_key(tree, "planned")])
        )
        self.assertTrue(
            all([value == 0 for value in self.get_all_values_for_key(tree, "done")])
        )
        self.assertTrue(
            all([value == 0 for value in self.get_all_values_for_key(tree, "wip")])
        )
        self.assertTrue(
            all([value == 0 for value in self.get_all_values_for_key(tree, "floor")])
        )
        # Check for the bulk product material
        self.assertEqual(tree["quantities"]["initial_planned"], FACTOR * QTY)
        self.assertEqual(
            len(tree["upstream_branches"]), 1
        )  # Should only be a single upstream line
        self.assertEqual(
            tree["upstream_branches"][0]["quantities"]["initial_planned"], QTY
        )
        # is the correct factor used between int product and bulk
        self.assertEqual(tree["upstream_branches"][0]["ratio"], FACTOR)

    # --- Business Logic & Validations ---

    def test_validate_json_production_malformed(self):
        campaign, demand = self.create_full_campaign(self.int_prod_y_blue, 100)
        campaign.action_plan()
        wizard = self.wizard.create({"campaign_id": campaign.id})
        data = {}
        with self.assertRaises(ValidationError):
            wizard._validate_json_production(data)

    def test_validate_json_production_wrong_campaign(self):
        PRODUCT = self.int_prod_y_blue
        campaign_1, _ = self.create_full_campaign(PRODUCT, 100)
        campaign_2, _ = self.create_full_campaign(PRODUCT, 100)

        campaign_1.action_plan()
        campaign_2.action_plan()

        wrong_line = campaign_2.line_ids.filtered_domain(
            [("product_id", "=", self.bulk_material.id)]
        )

        wizard = self.wizard.create({"campaign_id": campaign_1.id})
        data = self.wizard._make_partition_json(campaign_1)

        data["tree"]["line_id"] = wrong_line.id
        with self.assertRaises(ValidationError):
            wizard._validate_json_production(data)

    def test_validate_json_production_bad_id(self):
        campaign, _ = self.create_full_campaign(self.int_prod_y_blue, 100)
        campaign.action_plan()

        wizard = self.wizard.create({"campaign_id": campaign.id})
        data = self.wizard._make_partition_json(campaign)

        data["tree"]["line_id"] = 98456123
        with self.assertRaises(ValidationError):
            wizard._validate_json_production(data)

    def test_validate_json_production_wrong_line(self):
        QTY = 100.0
        PRODUCT = self.int_prod_x_red
        ALT_PRODUCT = self.int_prod_x_blue

        campaign, _ = self.create_full_campaign(PRODUCT, QTY)
        alt_campaign, _ = self.create_full_campaign(ALT_PRODUCT, QTY)
        campaign.action_plan()
        alt_campaign.action_plan()

        wizard = self.wizard.create({"campaign_id": campaign.id})
        campaign_lines = campaign.line_ids
        alt_line = alt_campaign.line_ids[0]

        self.assertEqual(len(campaign_lines), 2)
        data = wizard._make_partition_json(campaign)
        data["tree"]["upstream_branches"][0]["line_id"] = alt_line.id

        with self.assertRaises(ValidationError):
            wizard._validate_json_production(data)

    def test_validate_json_production_valid(self):
        PRODUCT = self.int_prod_y_blue
        campaign, _ = self.create_full_campaign(PRODUCT, 100)
        campaign.action_plan()
        campaign_lines = campaign.line_ids

        self.assertEqual(len(campaign_lines), 2)

        int_line = campaign_lines.filtered_domain([("product_id", "=", PRODUCT.id)])
        bulk_line = campaign_lines - int_line

        wizard = self.wizard.create({"campaign_id": campaign.id})
        data = self.wizard._make_partition_json(campaign)

        expected = {
            bulk_line.id: (
                bulk_line,
                {k: v for k, v in data["tree"].items() if k != "upstream_branches"},
            ),
            int_line.id: (
                int_line,
                {
                    k: v
                    for k, v in data["tree"]["upstream_branches"][0].items()
                    if k != "upstream_branches"
                },
            ),
        }

        result = wizard._validate_json_production(data)

        self.assertEqual(len(result.keys()), len(set(result.keys())))

        self.assertSetEqual(
            set(expected.keys()),
            set(result.keys()),
        )

        self.assertDictEqual(result, expected)

    def test_get_deltas_production_valid_non_zero(self):
        QTY = 100.0
        RATIO = 3.0  # 3 bulk for 1 int
        PRODUCT = self.int_prod_x_red
        campaign, _ = self.create_full_campaign(PRODUCT, QTY)
        campaign.action_plan()
        wizard = self.wizard.create({"campaign_id": campaign.id})
        campaign_lines = campaign.line_ids

        self.assertEqual(len(campaign_lines), 2)
        int_line = campaign_lines.filtered_domain([("product_id", "=", PRODUCT.id)])
        bulk_line = campaign_lines - int_line

        # No changes to the data, so nothing was allocated
        # Equivalent to backordering everthing
        data = wizard._make_partition_json(campaign)
        lines = wizard._validate_json_production(data)

        expected = {
            bulk_line.id: (bulk_line, QTY * RATIO),
            int_line.id: (int_line, QTY),
        }

        deltas = wizard._get_deltas_production(lines)

        self.assertDictEqual(expected, deltas)

    def test_get_deltas_production_valid_zero(self):
        QTY = 100.0
        PRODUCT = self.int_prod_x_red
        campaign, _ = self.create_full_campaign(PRODUCT, QTY)
        campaign.action_plan()
        wizard = self.wizard.create({"campaign_id": campaign.id})
        campaign_lines = campaign.line_ids

        self.assertEqual(len(campaign_lines), 2)

        data = wizard._make_partition_json(campaign)
        # We assign everything. Equivalent to no backorder
        # planned quantities == initial_planned quantities
        data["tree"]["quantities"]["planned"] = data["tree"]["quantities"][
            "initial_planned"
        ]
        data["tree"]["upstream_branches"][0]["quantities"]["planned"] = data["tree"][
            "upstream_branches"
        ][0]["quantities"]["initial_planned"]

        lines = wizard._validate_json_production(data)

        expected = {}
        deltas = wizard._get_deltas_production(lines)

        self.assertDictEqual(expected, deltas)

    def test_get_deltas_production_wrong_product(self):
        QTY = 100.0
        PRODUCT = self.int_prod_x_red
        ALT_PRODUCT = self.int_prod_x_blue

        campaign, _ = self.create_full_campaign(PRODUCT, QTY)
        campaign.action_plan()
        wizard = self.wizard.create({"campaign_id": campaign.id})
        campaign_lines = campaign.line_ids

        self.assertEqual(len(campaign_lines), 2)

        data = wizard._make_partition_json(campaign)
        data["tree"]["upstream_branches"][0]["product_id"] = ALT_PRODUCT.id

        lines = wizard._validate_json_production(data)

        with self.assertRaises(ValidationError):
            wizard._get_deltas_production(lines)

    def test_get_deltas_production_under_commit(self):
        QTY = 100.0
        FACTOR = 3.0
        PRODUCT = self.int_prod_x_red

        campaign, _ = self.create_full_campaign(PRODUCT, QTY)
        campaign.action_plan()
        campaign.action_confirm()

        mos = campaign.production_ids
        bulk_mo = mos.filtered_domain([("product_id", "=", self.bulk_material.id)])

        # set producing qty to half of the total qty
        bulk_mo.qty_producing = QTY * FACTOR / 2
        floor = QTY * FACTOR / 2

        wizard = self.wizard.create({"campaign_id": campaign.id})

        data = wizard._make_partition_json(campaign)
        # We set it lower than the max quantity
        data["tree"]["quantities"]["planned"] = floor
        self.assertLess(
            data["tree"]["quantities"]["planned"], data["tree"]["quantities"]["floor"]
        )
        lines = wizard._validate_json_production(data)
        with self.assertRaises(ValidationError):
            wizard._get_deltas_production(lines)

    def test_validate_json_demand_valid(self):
        campaign, demand = self.create_full_campaign(self.bulk_material, 100)
        proxy = demand.demand_proxy_ids[0]
        data = {"demand_moves": [{"proxy_id": proxy.id}]}
        wizard = self.wizard.create({"campaign_id": campaign.id})

        mapped_data = wizard._validate_json_demand(data)

        self.assertTrue(mapped_data.get(proxy.id, False))
        self.assertEqual(mapped_data[proxy.id], (proxy, {"proxy_id": proxy.id}))

    def test_validate_json_demand_wrong_campaign_for_proxy(self):
        campaign, demand_1 = self.create_full_campaign(self.bulk_material, 100)
        _, demand_2 = self.create_full_campaign(self.bulk_material, 100)
        wizard = self.wizard.create({"campaign_id": campaign.id})
        data = {"demand_moves": [{"proxy_id": demand_2.demand_proxy_ids[0].id}]}

        with self.assertRaises(ValidationError):
            wizard._validate_json_demand(data)

    def test_validate_json_demand_wrong_bad_id(self):
        campaign, demand = self.create_full_campaign(self.bulk_material, 100)
        data = {"demand_moves": [{"proxy_id": 31276894021}]}
        wizard = self.wizard.create({"campaign_id": campaign.id})

        with self.assertRaises(ValidationError):
            wizard._validate_json_demand(data)

    def test_validate_json_demand_malformed(self):
        campaign, demand = self.create_full_campaign(self.bulk_material, 100)
        data = {}
        wizard = self.wizard.create({"campaign_id": campaign.id})

        with self.assertRaises(ValidationError):
            wizard._validate_json_demand(data)

    def test_delta_calculation_demand_non_zero(self):
        QTY = 100.0
        FULFILLED = 50.0
        DELTA = 50.0
        campaign, demand = self.create_full_campaign(self.bulk_material, QTY)
        proxy = demand.demand_proxy_ids[0]
        lines = {proxy.id: (proxy, {"fulfilled_qty": FULFILLED})}
        wizard = self.wizard.create({"campaign_id": campaign.id})
        delta = wizard._get_deltas_demand(lines)
        self.assertTrue(delta.get(proxy.id, False))
        self.assertEqual(delta[proxy.id][0], proxy)
        self.assertEqual(delta[proxy.id][1], DELTA)

    def test_delta_calculation_demand_negative(self):
        QTY = 100.0
        FULFILLED = -50.0
        campaign, demand = self.create_full_campaign(self.bulk_material, QTY)
        proxy = demand.demand_proxy_ids[0]
        lines = {proxy.id: (proxy, {"fulfilled_qty": FULFILLED})}
        wizard = self.wizard.create({"campaign_id": campaign.id})
        with self.assertRaises(ValidationError):
            wizard._get_deltas_demand(lines)

    def test_delta_calculation_demand_zero(self):
        QTY = 100.0
        FULFILLED = 100.0
        campaign, demand = self.create_full_campaign(self.bulk_material, QTY)
        proxy = demand.demand_proxy_ids[0]
        lines = {proxy.id: (proxy, {"fulfilled_qty": FULFILLED})}
        wizard = self.wizard.create({"campaign_id": campaign.id})
        delta = wizard._get_deltas_demand(lines)
        self.assertFalse(delta)

    def test_delta_calculation_demand_overflow(self):
        QTY = 100.0
        FULFILLED = 150
        campaign, demand = self.create_full_campaign(self.bulk_material, QTY)
        proxy = demand.demand_proxy_ids[0]
        lines = {proxy.id: (proxy, {"fulfilled_qty": FULFILLED})}
        wizard = self.wizard.create({"campaign_id": campaign.id})
        with self.assertRaises(ValidationError):
            wizard._get_deltas_demand(lines)
