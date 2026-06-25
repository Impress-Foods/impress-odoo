import logging
from unittest.mock import MagicMock, patch

import requests

from odoo.tests import common

from ..models.schema import DominoLabel, DominoPrinter

_logger = logging.getLogger(__name__)


class TestDominoAPI(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param(
            "domino_printing.api_endpoint", "https://domino.test/api/"
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "domino_printing.api_key", "test-key-123"
        )

    def _get_api(self):
        from ..models.domino import DominoAPI

        return DominoAPI(self.env)

    @patch("odoo.addons.domino_printing.models.domino.requests.Session.get")
    def test_make_api_request_get_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_get.return_value = mock_response

        api = self._get_api()
        response = api._make_api_request("/labels", "GET")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        mock_get.assert_called_once()

    @patch("odoo.addons.domino_printing.models.domino.requests.Session.post")
    def test_make_api_request_post_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 42}
        mock_post.return_value = mock_response

        api = self._get_api()
        response = api._make_api_request("/printers/1/print", "POST", {"key": "val"})

        self.assertEqual(response.status_code, 201)
        mock_post.assert_called_once()

    @patch("odoo.addons.domino_printing.models.domino.requests.Session.get")
    def test_make_api_request_connection_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("DNS failure")

        api = self._get_api()
        with self.assertRaises(requests.ConnectionError):
            api._make_api_request("/labels", "GET")

    @patch("odoo.addons.domino_printing.models.domino.requests.Session.get")
    def test_make_api_request_timeout(self, mock_get):
        mock_get.side_effect = requests.Timeout("timed out")

        api = self._get_api()
        with self.assertRaises(requests.Timeout):
            api._make_api_request("/labels", "GET")

    @patch("odoo.addons.domino_printing.models.domino.requests.Session.get")
    def test_get_labels_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 1, "name": "Label A", "printer_ids": [1, 2]},
            {"id": 2, "name": "Label B", "printer_ids": []},
        ]
        mock_get.return_value = mock_response

        api = self._get_api()
        result = api.get_labels()

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], DominoLabel)
        self.assertEqual(result[0].name, "Label A")
        self.assertEqual(result[1].name, "Label B")

    @patch("odoo.addons.domino_printing.models.domino.requests.Session.get")
    def test_get_labels_non_200(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        api = self._get_api()
        result = api.get_labels()
        self.assertIsNone(result)

    @patch("odoo.addons.domino_printing.models.domino.requests.Session.get")
    def test_get_labels_malformed_json(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("bad json")
        mock_get.return_value = mock_response

        api = self._get_api()
        result = api.get_labels()
        self.assertIsNone(result)

    @patch("odoo.addons.domino_printing.models.domino.requests.Session.get")
    def test_get_printers_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 1, "name": "Printer 1", "active": True},
            {"id": 2, "name": "Printer 2", "active": False},
        ]
        mock_get.return_value = mock_response

        api = self._get_api()
        result = api.get_printers()

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], DominoPrinter)
        self.assertEqual(result[0].name, "Printer 1")
        self.assertTrue(result[0].active)
        self.assertFalse(result[1].active)

    @patch("odoo.addons.domino_printing.models.domino.requests.Session.post")
    def test_send_print_job_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        api = self._get_api()
        result = api.send_print_job(1, "label_a", {"key": "val"})

        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch("odoo.addons.domino_printing.models.domino.requests.Session.post")
    def test_send_print_job_201(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        api = self._get_api()
        result = api.send_print_job(1, "label_a", {"key": "val"})

        self.assertTrue(result)

    @patch("odoo.addons.domino_printing.models.domino.requests.Session.post")
    def test_send_print_job_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        api = self._get_api()
        result = api.send_print_job(1, "label_a", {"key": "val"})

        self.assertFalse(result)

    @patch("odoo.addons.domino_printing.models.domino.requests.Session.post")
    def test_send_print_job_connection_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("printer offline")

        api = self._get_api()
        result = api.send_print_job(1, "label_a", {"key": "val"})

        self.assertFalse(result)
