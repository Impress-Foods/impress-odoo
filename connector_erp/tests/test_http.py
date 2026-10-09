from unittest import mock

from requests import exceptions as req_exceptions

from odoo.tests import TransactionCase

from odoo.addons.connector.exception import NetworkRetryableError
from odoo.addons.connector_erp.services.http import HTTPClient


class TestHTTPClient(TransactionCase):
    def _make_client(self):
        backend = mock.Mock(base_url="https://example.com/", api_key="token")
        return HTTPClient(backend)

    def test_retryable_status_code_is_retryable(self):
        client = self._make_client()
        response = mock.Mock(status_code=429)
        with mock.patch(
            "odoo.addons.connector_erp.services.http.requests.request",
            return_value=response,
        ):
            with self.assertRaises(NetworkRetryableError):
                client.request("orders")

    def test_connection_error_is_retryable(self):
        client = self._make_client()
        with mock.patch(
            "odoo.addons.connector_erp.services.http.requests.request",
            side_effect=req_exceptions.ConnectionError("boom"),
        ):
            with self.assertRaises(NetworkRetryableError):
                client.request("orders")

    def test_client_error_is_not_retryable(self):
        client = self._make_client()
        response = mock.Mock(status_code=404)
        response.raise_for_status.side_effect = req_exceptions.HTTPError(
            "404 Client Error"
        )
        with mock.patch(
            "odoo.addons.connector_erp.services.http.requests.request",
            return_value=response,
        ):
            with self.assertRaises(req_exceptions.HTTPError):
                client.request("orders")

    def test_successful_response_is_returned(self):
        client = self._make_client()
        response = mock.Mock(status_code=200)
        with mock.patch(
            "odoo.addons.connector_erp.services.http.requests.request",
            return_value=response,
        ) as request_mock:
            result = client.request("orders")

        self.assertIs(result, response)
        self.assertEqual(request_mock.call_args.args[1], "https://example.com/orders")
