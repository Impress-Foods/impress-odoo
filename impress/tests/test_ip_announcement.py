from unittest import mock

import requests

from odoo.tests import HttpCase, tagged

URL_PARAM = "impress.ip_announce.url"
TOKEN_PARAM = "impress.ip_announce.token"
ROUTE = "/_odoo.sh/ip-change?old=203.0.113.10&new=203.0.113.20"


@tagged("post_install", "-at_install")
class TestIPChangeRoute(HttpCase):
    def setUp(self):
        super().setUp()
        self.params = self.env["ir.config_parameter"].sudo()
        self.params.set_param(URL_PARAM, "https://hooks.example.test/ip")
        patcher = mock.patch.object(requests, "post")
        self.post = patcher.start()
        self.addCleanup(patcher.stop)

    def test_forwards_change_and_returns_ok(self):
        response = self.url_open(ROUTE)
        self.assertEqual(response.text, "ok")
        self.post.assert_called_once_with(
            "https://hooks.example.test/ip",
            json={"ip": "203.0.113.20"},
            headers={},
            timeout=5,
        )

    def test_token_is_sent_as_bearer_header(self):
        self.params.set_param(TOKEN_PARAM, "secret")
        self.url_open(ROUTE)
        self.assertEqual(
            self.post.call_args.kwargs["headers"], {"Authorization": "Bearer secret"}
        )

    def test_no_url_configured_sends_nothing(self):
        self.params.set_param(URL_PARAM, False)
        response = self.url_open(ROUTE)
        self.assertEqual(response.text, "ok")
        self.post.assert_not_called()

    def test_webserver_failure_still_returns_ok(self):
        self.post.side_effect = requests.ConnectionError("unreachable")
        response = self.url_open(ROUTE)
        self.assertEqual(response.text, "ok")
