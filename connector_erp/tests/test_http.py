from unittest import mock

from requests import exceptions as req_exceptions

from odoo.tests import TransactionCase

from odoo.addons.connector.exception import NetworkRetryableError
from odoo.addons.connector_erp.services.http import HTTPClient


class CustomAuthClient(HTTPClient):
    def _auth_headers(self):
        return {"Authorization": "Bearer custom-token", "X-Custom": "1"}


class TestHTTPClient(TransactionCase):
    def _make_client(self, client_class=HTTPClient, **backend_values):
        values = {"base_url": "https://example.com/", "api_key": "token"}
        values.update(backend_values)
        return client_class(mock.Mock(**values))

    def _request_mock(self, response=None, side_effect=None):
        return mock.patch(
            "odoo.addons.connector_erp.services.http.requests.request",
            return_value=response,
            side_effect=side_effect,
        )

    def test_retryable_status_code_is_retryable(self):
        client = self._make_client()
        with self._request_mock(mock.Mock(status_code=429)):
            with self.assertRaises(NetworkRetryableError):
                client.request("orders")

    def test_connection_error_is_retryable(self):
        client = self._make_client()
        with self._request_mock(side_effect=req_exceptions.ConnectionError("boom")):
            with self.assertRaises(NetworkRetryableError):
                client.request("orders")

    def test_client_error_is_not_retryable(self):
        client = self._make_client()
        response = mock.Mock(status_code=404)
        response.raise_for_status.side_effect = req_exceptions.HTTPError(
            "404 Client Error"
        )
        with self._request_mock(response):
            with self.assertRaises(req_exceptions.HTTPError):
                client.request("orders")

    def test_successful_response_is_returned(self):
        client = self._make_client()
        response = mock.Mock(status_code=200)
        with self._request_mock(response) as request_mock:
            result = client.request("orders")

        self.assertIs(result, response)
        self.assertEqual(request_mock.call_args.args[1], "https://example.com/orders")

    def test_json_body_is_sent(self):
        client = self._make_client()
        response = mock.Mock(status_code=200)
        with self._request_mock(response) as request_mock:
            client.request("orders", method="POST", json={"name": "Alice"})

        self.assertEqual(request_mock.call_args.kwargs["json"], {"name": "Alice"})
        self.assertIsNone(request_mock.call_args.kwargs["data"])

    def test_default_auth_header_is_bearer(self):
        client = self._make_client()
        response = mock.Mock(status_code=200)
        with self._request_mock(response) as request_mock:
            client.request("orders")

        headers = request_mock.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer token")
        self.assertEqual(headers["Accept"], "application/json")

    def test_per_call_headers_are_merged(self):
        client = self._make_client()
        response = mock.Mock(status_code=200)
        with self._request_mock(response) as request_mock:
            client.request("orders", headers={"X-Request-Id": "abc"})

        headers = request_mock.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Request-Id"], "abc")
        self.assertEqual(headers["Authorization"], "Bearer token")

    def test_auth_headers_can_be_overridden(self):
        client = self._make_client(client_class=CustomAuthClient)
        response = mock.Mock(status_code=200)
        with self._request_mock(response) as request_mock:
            client.request("orders")

        headers = request_mock.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer custom-token")
        self.assertEqual(headers["X-Custom"], "1")

    def test_unauthenticated_request_omits_auth_header(self):
        client = self._make_client()
        response = mock.Mock(status_code=200)
        with self._request_mock(response) as request_mock:
            client.request_unauthenticated(
                "oauth2/token", data={"grant_type": "client_credentials"}
            )

        headers = request_mock.call_args.kwargs["headers"]
        self.assertNotIn("Authorization", headers)
        self.assertEqual(headers["Accept"], "application/json")
        self.assertEqual(
            request_mock.call_args.kwargs["data"],
            {"grant_type": "client_credentials"},
        )

    def test_build_url_keeps_the_base_path(self):
        client = self._make_client(base_url="https://api.example.com/api/v3")
        self.assertEqual(
            client._build_url("/oauth2/token"),
            "https://api.example.com/api/v3/oauth2/token",
        )
        self.assertEqual(
            client._build_url("orders"),
            "https://api.example.com/api/v3/orders",
        )
