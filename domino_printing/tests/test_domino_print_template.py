import logging

from odoo.exceptions import ValidationError
from odoo.tests import common

_logger = logging.getLogger(__name__)


class TestDominoPrintTemplate(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.Model = self.env["domino.print.template"]
        self.FieldModel = self.env["domino.print.field"]
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
        self.label = self.env["domino.label"].create({"name": "Label A"})

    def _make_check(self):
        return self.env["quality.check"].create(
            {
                "team_id": self.team.id,
                "test_type_id": self.test_type.id,
                "product_id": self.product.id,
            }
        )

    def test_validate_payload_missing_text_field_raises(self):
        template = self.Model.create(
            {
                "name": "Test Template",
                "print_type": "code",
                "domino_label_id": self.label.id,
                "field_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "code_field",
                            "field_type": "dynamic",
                            "target_field": "PRODUCT_CODE",
                            "odoo_field_path": "product_id.default_code",
                            "required": True,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(ValidationError):
            template._validate_payload({}, [])

    def test_validate_payload_text_field_present(self):
        template = self.Model.create(
            {
                "name": "Test Template",
                "print_type": "code",
                "domino_label_id": self.label.id,
                "field_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "code_field",
                            "field_type": "dynamic",
                            "target_field": "PRODUCT_CODE",
                            "odoo_field_path": "product_id.default_code",
                            "required": True,
                        },
                    )
                ],
            }
        )
        template._validate_payload({"PRODUCT_CODE": "ABC"}, [])
        self.assertTrue(True)

    def test_validate_payload_missing_data_field_raises(self):
        template = self.Model.create(
            {
                "name": "Test Template",
                "print_type": "code",
                "domino_label_id": self.label.id,
                "field_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "batch_field",
                            "field_type": "data",
                            "target_field": "BATCH",
                            "data_id": 1,
                            "data_value": "B001",
                            "required": True,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(ValidationError):
            template._validate_payload({}, [])

    def test_validate_payload_data_field_present(self):
        template = self.Model.create(
            {
                "name": "Test Template",
                "print_type": "code",
                "domino_label_id": self.label.id,
                "field_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "batch_field",
                            "field_type": "data",
                            "target_field": "BATCH",
                            "data_id": 1,
                            "data_value": "B001",
                            "required": True,
                        },
                    )
                ],
            }
        )
        template._validate_payload({}, [{"name": "BATCH", "id": 1, "value": "B001"}])
        self.assertTrue(True)

    def test_validate_payload_required_not_set_not_checked(self):
        template = self.Model.create(
            {
                "name": "Test Template",
                "print_type": "code",
                "domino_label_id": self.label.id,
                "field_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "optional_field",
                            "field_type": "dynamic",
                            "target_field": "OPTIONAL",
                            "odoo_field_path": "product_id.default_code",
                            "required": False,
                        },
                    )
                ],
            }
        )
        template._validate_payload({}, [])
        self.assertTrue(True)

    def test_make_json_payload(self):
        field_code = self.FieldModel.create(
            {
                "name": "code_field",
                "field_type": "dynamic",
                "target_field": "PRODUCT_CODE",
                "odoo_field_path": "product_id.default_code",
            }
        )
        field_batch = self.FieldModel.create(
            {
                "name": "batch_field",
                "field_type": "data",
                "target_field": "BATCH",
                "data_id": 1,
                "data_value": "B001",
            }
        )
        template = self.Model.create(
            {
                "name": "Test Template",
                "print_type": "code",
                "domino_label_id": self.label.id,
                "field_ids": [(6, 0, (field_code + field_batch).ids)],
            }
        )

        check = self._make_check()
        result = template._make_json_payload(check)

        self.assertIn("textFields", result)
        self.assertIn("dataFields", result)
        self.assertEqual(result["textFields"], {"PRODUCT_CODE": "ABC123"})
        self.assertEqual(
            result["dataFields"],
            [{"name": "BATCH", "id": 1, "value": "B001"}],
        )
