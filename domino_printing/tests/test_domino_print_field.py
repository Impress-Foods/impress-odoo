import logging
from datetime import date, datetime
from unittest.mock import MagicMock

from odoo.exceptions import ValidationError
from odoo.tests import common

_logger = logging.getLogger(__name__)


class TestFormatDate(common.TransactionCase):
    def test_std_format(self):
        result = self.env["domino.print.field"]._format_date(
            date(2024, 3, 15), "%Y-%m-%d"
        )
        self.assertEqual(result, "2024-03-15")

    def test_can_month_abbreviation(self):
        result = self.env["domino.print.field"]._format_date(date(2024, 3, 15), "%q/%Y")
        self.assertEqual(result, "MR/2024")

    def test_can_month_abbreviation_january(self):
        result = self.env["domino.print.field"]._format_date(date(2024, 1, 1), "%q/%Y")
        self.assertEqual(result, "JA/2024")

    def test_can_month_abbreviation_december(self):
        result = self.env["domino.print.field"]._format_date(
            date(2024, 12, 25), "%q-%d-%Y"
        )
        self.assertEqual(result, "DE-25-2024")

    def test_datetime_input(self):
        result = self.env["domino.print.field"]._format_date(
            datetime(2024, 6, 15, 14, 30), "%Y-%m-%d %H:%M"
        )
        self.assertEqual(result, "2024-06-15 14:30")

    def test_can_month_without_q_passes_through(self):
        result = self.env["domino.print.field"]._format_date(date(2024, 3, 15), "%b/%Y")
        self.assertEqual(result, "Mar/2024")


class TestTransformValue(common.TransactionCase):
    def test_no_transform(self):
        result = self.env["domino.print.field"]._transform_value("hello", None)
        self.assertEqual(result, "hello")

    def test_empty_transform(self):
        result = self.env["domino.print.field"]._transform_value("hello", "")
        self.assertEqual(result, "hello")

    def test_upper(self):
        result = self.env["domino.print.field"]._transform_value("hello", "upper")
        self.assertEqual(result, "HELLO")

    def test_lower(self):
        result = self.env["domino.print.field"]._transform_value("HELLO", "lower")
        self.assertEqual(result, "hello")

    def test_date_transform(self):
        result = self.env["domino.print.field"]._transform_value(
            date(2024, 3, 15), "%Y-%m-%d"
        )
        self.assertEqual(result, "2024-03-15")

    def test_unknown_transform_is_noop(self):
        result = self.env["domino.print.field"]._transform_value("hello", "reverse")
        self.assertEqual(result, "hello")


class TestGetFieldValue(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.Model = self.env["domino.print.field"]
        self.team = self.env["quality.alert.team"].create({"name": "Test Team"})
        self.test_type = self.env["quality.point.test_type"].create(
            {
                "name": "Test Type",
                "technical_name": "test_type",
            }
        )
        self.product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "default_code": "ABC123",
            }
        )

    def _make_check(self, product=None):
        return self.env["quality.check"].create(
            {
                "team_id": self.team.id,
                "test_type_id": self.test_type.id,
                "product_id": product.id if product else False,
            }
        )

    def test_dynamic_valid(self):
        field = self.Model.create(
            {
                "name": "test_dynamic",
                "field_type": "dynamic",
                "odoo_field_path": "product_id.default_code",
                "target_field": "CODE",
            }
        )
        check = self._make_check(self.product)
        result = field.get_field_value(check)
        self.assertEqual(result, "ABC123")

    def test_dynamic_with_transform(self):
        field = self.Model.create(
            {
                "name": "test_dynamic_upper",
                "field_type": "dynamic",
                "odoo_field_path": "product_id.default_code",
                "target_field": "CODE",
                "transform": "upper",
            }
        )
        check = self._make_check(self.product)
        result = field.get_field_value(check)
        self.assertEqual(result, "ABC123")

    def test_dynamic_empty_value_raises(self):
        field = self.Model.create(
            {
                "name": "test_dynamic_empty",
                "field_type": "dynamic",
                "odoo_field_path": "product_id.default_code",
                "target_field": "CODE",
            }
        )
        check = self._make_check()
        with self.assertRaises(ValidationError):
            field.get_field_value(check)

    def test_dynamic_empty_field_no_default_raises(self):
        product = self.env["product.product"].create({"name": "No Code Product"})
        field = self.Model.create(
            {
                "name": "test_dynamic_empty_no_default",
                "field_type": "dynamic",
                "odoo_field_path": "product_id.default_code",
                "target_field": "CODE",
            }
        )
        check = self._make_check(product)
        with self.assertRaises(ValidationError):
            field.get_field_value(check)

    def test_dynamic_empty_field_with_default_returns_default(self):
        product = self.env["product.product"].create({"name": "Fallback Product"})
        field = self.Model.create(
            {
                "name": "test_dynamic_empty_with_default",
                "field_type": "dynamic",
                "odoo_field_path": "product_id.default_code",
                "target_field": "CODE",
                "default_value": "FALLBACK",
            }
        )
        check = self._make_check(product)
        result = field.get_field_value(check)
        self.assertEqual(result, "FALLBACK")

    def test_dynamic_multiple_values_raises(self):
        field = self.Model.create(
            {
                "name": "test_dynamic_multi",
                "field_type": "dynamic",
                "odoo_field_path": "product_id.default_code",
                "target_field": "CODE",
            }
        )
        source = MagicMock()
        source.mapped.return_value = ["A", "B"]
        with self.assertRaises(ValidationError):
            field.get_field_value(source)

    def test_static_returns_default(self):
        field = self.Model.create(
            {
                "name": "test_static",
                "field_type": "static",
                "target_field": "PLANT",
                "default_value": "Plant1",
            }
        )
        result = field.get_field_value(None)
        self.assertEqual(result, "Plant1")

    def test_data_returns_dict(self):
        field = self.Model.create(
            {
                "name": "test_data",
                "field_type": "data",
                "target_field": "batch_id",
                "data_id": 42,
                "data_value": "BATCH-001",
            }
        )
        result = field.get_field_value(None)
        self.assertEqual(result, {"name": "batch_id", "id": 42, "value": "BATCH-001"})
