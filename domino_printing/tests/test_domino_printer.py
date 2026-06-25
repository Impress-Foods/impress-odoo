import logging
from unittest.mock import patch

from odoo.tests import common

_logger = logging.getLogger(__name__)


class TestSyncPrinters(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.Model = self.env["domino.printer"]

    def _make_printer(self, domino_id, name, active=True):
        from ..models.schema import DominoPrinter

        return DominoPrinter(id=domino_id, name=name, active=active)

    @patch("odoo.addons.domino_printing.models.domino.DominoAPI.get_printers")
    def test_sync_creates_new_printers(self, mock_get_printers):
        mock_get_printers.return_value = [
            self._make_printer(1, "Printer Alpha"),
            self._make_printer(2, "Printer Beta", active=True),
        ]

        self.Model._sync_printers()

        Model = self.Model.with_context(active_test=False)
        self.assertEqual(Model.search_count([("printer_id", "=", 1)]), 1)
        self.assertEqual(Model.search_count([("printer_id", "=", 2)]), 1)

    @patch("odoo.addons.domino_printing.models.domino.DominoAPI.get_printers")
    def test_sync_updates_existing_printers(self, mock_get_printers):
        existing = self.Model.create({"name": "Old Name", "printer_id": 1})

        mock_get_printers.return_value = [
            self._make_printer(1, "Updated Name"),
        ]

        self.Model._sync_printers()

        self.assertEqual(existing.name, "Updated Name")

    @patch("odoo.addons.domino_printing.models.domino.DominoAPI.get_printers")
    def test_sync_updates_active_status(self, mock_get_printers):
        existing = self.Model.create(
            {"name": "Printer", "printer_id": 1, "active": True}
        )

        mock_get_printers.return_value = [
            self._make_printer(1, "Printer", active=False),
        ]

        self.Model._sync_printers()

        self.assertFalse(existing.active)

    @patch("odoo.addons.domino_printing.models.domino.DominoAPI.get_printers")
    def test_sync_deletes_stale_printers(self, mock_get_printers):
        self.Model.create({"name": "Stale", "printer_id": 1})

        mock_get_printers.return_value = [
            self._make_printer(2, "Still Alive"),
        ]

        self.Model._sync_printers()

        self.assertEqual(self.Model.search_count([("printer_id", "=", 1)]), 0)

    @patch("odoo.addons.domino_printing.models.domino.DominoAPI.get_printers")
    def test_sync_api_failure_skips_safely(self, mock_get_printers):
        existing = self.Model.create({"name": "Keep Me", "printer_id": 1})

        mock_get_printers.return_value = None

        self.Model._sync_printers()

        self.assertEqual(existing.name, "Keep Me")
        self.assertEqual(self.Model.search_count([]), 1)

    @patch("odoo.addons.domino_printing.models.domino.DominoAPI.get_printers")
    def test_sync_empty_response_does_not_delete(self, mock_get_printers):
        self.Model.create({"name": "Only Printer", "printer_id": 1})

        mock_get_printers.return_value = []

        self.Model._sync_printers()

        self.assertEqual(self.Model.search_count([]), 1)

    @patch("odoo.addons.domino_printing.models.domino.DominoAPI.get_printers")
    def test_action_sync_printers(self, mock_get_printers):
        mock_get_printers.return_value = [
            self._make_printer(1, "Printer A"),
        ]

        self.Model.action_sync_printers()

        self.assertEqual(self.Model.search_count([("printer_id", "=", 1)]), 1)
