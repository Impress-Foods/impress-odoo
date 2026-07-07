import logging
from unittest.mock import patch

from odoo.tests import common

_logger = logging.getLogger(__name__)


class TestSyncLabels(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param(
            "domino_printing.api_endpoint", "https://domino.test/api/"
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "domino_printing.api_key", "test-key-123"
        )
        self.Model = self.env["domino.label"]
        self.PrinterModel = self.env["domino.printer"]

        self.printer_a = self.PrinterModel.create(
            {"name": "Printer A", "printer_id": 1}
        )
        self.printer_b = self.PrinterModel.create(
            {"name": "Printer B", "printer_id": 2}
        )

    def _make_label(self, domino_id, name, printer_ids=None):
        from ..models.schema import DominoLabel

        return DominoLabel(
            id=domino_id,
            name=name,
            printer_ids=printer_ids or [],
        )

    @patch("odoo.addons.domino_printing.models.domino.DominoAPI.get_labels")
    def test_sync_creates_new_labels(self, mock_get_labels):
        mock_get_labels.return_value = [
            self._make_label(1, "Label A", [1, 2]),
        ]

        self.Model._sync_labels()

        record = self.Model.search([("domino_id", "=", 1)])
        self.assertEqual(len(record), 1)
        self.assertEqual(record.name, "Label A")
        self.assertEqual(
            set(record.printer_ids.ids), {self.printer_a.id, self.printer_b.id}
        )

    @patch("odoo.addons.domino_printing.models.domino.DominoAPI.get_labels")
    def test_sync_updates_existing_labels(self, mock_get_labels):
        from ..models.schema import DominoBufferSchema, DominoField, DominoLabel

        schema = DominoBufferSchema(fields=[DominoField(name="FIELD1", type="text")])
        existing = self.Model.create(
            {"name": "Old Name", "domino_id": 1, "schema_json": "{}"}
        )

        mock_get_labels.return_value = [
            DominoLabel(
                id=1, name="Updated Label", printer_ids=[1], buffer_schema=schema
            ),
        ]

        self.Model._sync_labels()

        self.assertEqual(existing.schema_json, schema.model_dump_json())

    @patch("odoo.addons.domino_printing.models.domino.DominoAPI.get_labels")
    def test_sync_deletes_stale_labels(self, mock_get_labels):
        self.Model.create({"name": "Stale Label", "domino_id": 1})

        mock_get_labels.return_value = [
            self._make_label(2, "Still Alive"),
        ]

        self.Model._sync_labels()

        stale = self.Model.search([("domino_id", "=", 1)])
        self.assertEqual(len(stale), 0)

    @patch("odoo.addons.domino_printing.models.domino.DominoAPI.get_labels")
    def test_sync_api_failure_skips_safely(self, mock_get_labels):
        existing = self.Model.create({"name": "Keep Me", "domino_id": 1})

        mock_get_labels.return_value = None

        self.Model._sync_labels()

        self.assertEqual(existing.name, "Keep Me")
        self.assertEqual(self.Model.search_count([]), 1)

    @patch("odoo.addons.domino_printing.models.domino.DominoAPI.get_labels")
    def test_sync_handles_multiple_printers(self, mock_get_labels):
        self.PrinterModel.create({"name": "Printer C", "printer_id": 3})

        mock_get_labels.return_value = [
            self._make_label(1, "Multi Printer Label", [1, 3]),
        ]

        self.Model._sync_labels()

        record = self.Model.search([("domino_id", "=", 1)])
        self.assertEqual(len(record.printer_ids), 2)
