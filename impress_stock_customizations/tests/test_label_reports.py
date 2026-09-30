import datetime
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import common


class TestReportLabelBase(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.unit_uom = cls.env.ref("uom.product_uom_unit")
        cls.weight_uom_kg = cls.env.ref("uom.product_uom_kgm")
        cls.volume_uom_liter = cls.env.ref("uom.product_uom_litre")
        cls.weight_uom_g = cls.env.ref("uom.product_uom_gram")

        cls.product_tracking_none = cls._make_product(
            "Product No Tracking", "12345678901286", "none", cls.unit_uom
        )
        cls.product_tracking_lot = cls._make_product(
            "Product Lot Tracking", "21098765432108", "lot", cls.weight_uom_kg
        )
        cls.product_tracking_serial = cls._make_product(
            "Product Serial Tracking", "34567890123402", "serial", cls.volume_uom_liter
        )
        cls.product_no_barcode = cls._make_product(
            "Product No Barcode", False, "none", cls.unit_uom
        )
        cls.product_gtin12 = cls._make_product(
            "Product GTIN-12", "036000291452", "none", cls.unit_uom
        )

        cls.lot_lot = cls._make_lot("24558", cls.product_tracking_lot)
        cls.lot_serial = cls._make_lot("87453", cls.product_tracking_serial)

        cls.report = cls.env["report.impress_stock_customizations.label_base"]
        cls.nomenclature = cls.env.ref(
            "barcodes_gs1_nomenclature.default_gs1_nomenclature"
        )

    @classmethod
    def _make_product(cls, name, barcode, tracking, uom):
        product = cls.env["product.product"].create(
            {
                "name": name,
                "barcode": barcode,
                "type": "consu",
                "is_storable": True,
                "tracking": tracking,
                "uom_id": uom.id,
            }
        )
        return product

    @classmethod
    def _make_lot(cls, name, product):
        return cls.env["stock.lot"].create(
            {"name": name, "product_id": product.id, "company_id": cls.env.company.id}
        )

    def _assert_parsed_gs1(self, barcode, expected) -> None:
        """Verify that a GS1 barcode parses into the expected AI values."""
        parsed_results = self.nomenclature.parse_barcode(barcode)
        parsed_dict = {res["ai"]: res["value"] for res in parsed_results}
        for ai, expected_val in expected.items():
            self.assertIn(
                ai, parsed_dict, f"AI {ai} missing from parsed barcode {barcode}"
            )
            self.assertEqual(
                parsed_dict[ai],
                expected_val,
                f"Value mismatch for AI {ai} in barcode {barcode}. "
                f"Expected {expected_val}, got {parsed_dict[ai]}",
            )

    # -- report wiring -----------------------------------------------------

    def test_in_house_labels_are_dashboard_reports(self) -> None:
        """A report offered in the dashboard has to be flagged and be a label,
        and its rendering model must resolve."""
        report_model = self.env["ir.actions.report"]
        offered = report_model.search(
            report_model._dashboard_report_domain("stock.lot")
        )

        self.assertTrue(offered)
        for report in offered:
            self.assertTrue(report._is_dashboard_compatible())
            self.assertIsNotNone(report._get_rendering_context_model(report))

    def test_a_core_label_report_is_not_offered(self) -> None:
        report_model = self.env["ir.actions.report"]
        offered = report_model.search(
            report_model._dashboard_report_domain("stock.lot")
        )

        self.assertNotIn(self.env.ref("stock.label_product_product"), offered)

    def test_a_report_renders_one_label_body_per_copy(self) -> None:
        """The payload the dashboard builds has to render, and render the right
        number of labels; asserting the payload shape alone cannot catch a
        convention the report cannot consume."""
        report = self.env.ref("impress_stock_customizations.report_label_lot_zpl_2x4")
        dashboard = self.env["printing.dashboard"].create(
            {
                "target_model": "stock.lot",
                "product_id": self.lot_lot.product_id.id,
                "lot_id": self.lot_lot.id,
                "report_id": report.id,
                "printer_id": self._zpl_printer().id,
                "copies": 2,
                "product_uom_qty": 5,
                "product_uom_id": self.weight_uom_kg.id,
            }
        )

        with patch.object(
            type(dashboard.printer_id), "print_file", autospec=True
        ) as spy:
            dashboard.action_print()

        self.assertEqual(len(spy.call_args_list), 1)
        document, _fmt = report._render_qweb_text(
            report.report_name,
            [self.lot_lot.id],
            data=report._print_label_data(self.lot_lot, 2, 5, self.weight_uom_kg),
        )
        self.assertEqual(document.count(b"^XA"), 2)
        self.assertEqual(document.count(b"^XZ"), 2)

    def _zpl_printer(self):
        printer = self.env["printing.printer"].create(
            {
                "name": "ISCS ZPL Printer",
                "system_name": "iscs-zpl-printer",
                "backend": "base",
                "label_format": "zpl",
                "label_size": "2x4",
            }
        )
        return printer

    # -- GS1 barcode -------------------------------------------------------

    def test_gtin_is_padded_to_fourteen_digits(self) -> None:
        cases = [
            ("GTIN-12", self.product_gtin12, "00"),
            (
                "GTIN-13",
                self._make_product("G13", "1234567890128", "none", self.unit_uom),
                "0",
            ),
        ]
        for label, product, pad in cases:
            with self.subTest(label):
                expected = pad + product.barcode
                barcode = self.report._get_gs1_barcode(product_id=product)
                self.assertEqual(barcode, f"01{expected}")
                self._assert_parsed_gs1(barcode, {"01": expected})

    def test_an_unusable_product_raises(self) -> None:
        cases = [
            ("no product", False, {}),
            ("no barcode", self.product_no_barcode, {}),
            (
                "too long",
                self._make_product("Long", "123456789101112", "none", self.unit_uom),
                {},
            ),
            (
                "too short",
                self._make_product("Short", "12345678910", "none", self.unit_uom),
                {},
            ),
        ]
        for label, product, kwargs in cases:
            with self.subTest(label):
                if not product:
                    with self.assertRaises(ValidationError):
                        self.report._get_gs1_barcode()
                else:
                    with self.assertRaisesRegex(
                        ValidationError, "Product .* does not have a valid EAN"
                    ):
                        self.report._get_gs1_barcode(product_id=product, **kwargs)

    def test_quantity_encodes_the_matching_ai(self) -> None:
        """Counts use AI 30, weight 310n and volume 315n, at the precision the
        value carries."""
        cases = [
            ("count", self.product_tracking_none, 42, None, "30" + "00000042"),
            (
                "weight kg",
                self.product_tracking_lot,
                1.5,
                self.weight_uom_kg,
                "3101000015",
            ),
            (
                "volume",
                self.product_tracking_serial,
                1.5,
                self.volume_uom_liter,
                "3151000015",
            ),
            (
                "high precision",
                self.product_tracking_lot,
                1.234,
                self.weight_uom_kg,
                "3103001234",
            ),
            (
                "capped precision",
                self.product_tracking_lot,
                1.234567,
                self.weight_uom_kg,
                "3105123456",
            ),
            (
                "no integer part",
                self.product_tracking_lot,
                0.12345,
                self.weight_uom_kg,
                "3105012345",
            ),
            ("large", self.product_tracking_none, 99999999, None, "30" + "99999999"),
        ]
        for label, product, qty, uom, expected_suffix in cases:
            with self.subTest(label):
                barcode = self.report._get_gs1_barcode(
                    product_id=product, quantity=qty, uom=uom
                )

                self.assertEqual(barcode, f"01{product.barcode}{expected_suffix}")

    def test_a_zero_quantity_is_omitted(self) -> None:
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_none, quantity=0
        )

        self.assertEqual(barcode, f"01{self.product_tracking_none.barcode}")
        self.assertNotIn(
            "30", [res["ai"] for res in self.nomenclature.parse_barcode(barcode)]
        )

    def test_a_negative_quantity_raises(self) -> None:
        with self.assertRaises(ValidationError):
            self.report._get_gs1_barcode(
                product_id=self.product_tracking_none, quantity=-5
            )

    def test_a_lot_carries_its_serial_and_expiry(self) -> None:
        expiry = datetime.date(2026, 12, 31)
        self.lot_lot.expiration_date = expiry
        barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_lot,
            lot_id=self.lot_lot,
            quantity=1,
            uom=self.weight_uom_kg,
        )

        self._assert_parsed_gs1(
            barcode,
            {
                "01": self.product_tracking_lot.barcode.zfill(14),
                "3100": 1,
                "10": self.lot_lot.name,
                "17": expiry,
            },
        )

        serial_barcode = self.report._get_gs1_barcode(
            product_id=self.product_tracking_serial,
            lot_id=self.lot_serial,
            quantity=1,
            uom=self.volume_uom_liter,
        )
        self._assert_parsed_gs1(serial_barcode, {"21": self.lot_serial.name, "3150": 1})

    def test_the_quantity_code_is_ai_and_precision_plus_six_digits(self) -> None:
        cases = [
            (100, "310" + "0" + "000100"),
            (10.5, "310" + "1" + "000105"),
            (5.55, "310" + "2" + "000555"),
        ]
        for qty, expected in cases:
            with self.subTest(qty):
                self.assertEqual(
                    self.report._make_variable_decimal_code(qty, "310"), expected
                )

    # -- unit of measure resolution ---------------------------------------

    def test_the_closest_uom_reference_resolves_by_unit(self) -> None:
        cases = [
            (self.unit_uom, "uom.product_uom_unit"),
            (self.weight_uom_kg, "uom.product_uom_kgm"),
            (self.volume_uom_liter, "uom.product_uom_litre"),
            (self.weight_uom_g, "uom.product_uom_kgm"),
        ]
        for uom, reference in cases:
            with self.subTest(uom.display_name):
                result = self.report._get_closest_uom_reference(uom)
                self.assertIsNotNone(result)
                _resolved, ref = result
                self.assertEqual(ref, reference)

    def test_an_unresolvable_uom_returns_nothing(self) -> None:
        no_parent = self.env["uom.uom"].create(
            {"name": "Test UOM No Parent", "factor": 1.0}
        )

        self.assertIsNone(self.report._get_closest_uom_reference(no_parent))
        self.assertIsNone(self.report._get_closest_uom_reference(None))

    # -- label data --------------------------------------------------------

    def test_label_data_carries_the_count_and_unit(self) -> None:
        data = self.report._prepare_label_data(
            self.product_tracking_none, 10, self.unit_uom, 2
        )

        self.assertEqual(data["label_count"], 2)
        self.assertEqual(data["qty"], 10)
        self.assertEqual(data["unit_type"], "uom.product_uom_unit")

    def test_label_data_without_a_uom_omits_quantity(self) -> None:
        data = self.report._prepare_label_data(self.product_tracking_none, 10, None, 2)

        self.assertEqual(data["label_count"], 2)
        self.assertFalse(data.get("qty", False))
        self.assertFalse(data.get("unit_type", False))

    @patch(
        "odoo.addons.impress_stock_customizations.reports.label_data."
        "ReportLabelBase._get_closest_uom_reference"
    )
    def test_label_data_without_a_resolvable_unit_raises(
        self, mock_get_closest_uom_reference
    ) -> None:
        mock_get_closest_uom_reference.return_value = False

        with self.assertRaisesRegex(ValidationError, "Could not find base unit"):
            self.report._prepare_label_data(
                self.product_tracking_none, 10, self.unit_uom, 2
            )
