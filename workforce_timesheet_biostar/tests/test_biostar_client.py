from unittest import mock

import requests

from odoo.tests.common import TransactionCase

from odoo.addons.workforce_timesheet_biostar.models.biostar_client import (
    BiostarAPIError,
    BiostarAuthError,
    BiostarClient,
)

MODULE = "odoo.addons.workforce_timesheet_biostar.models.biostar_client"


class _FakeSession:
    """Minimal ``requests.Session`` stand-in with a scripted response queue."""

    def __init__(self, responses):
        self.headers = {}
        self.cookies = {}
        self.verify = True
        self._responses = list(responses)
        self.calls = []

    def request(self, method, url, timeout=None, **kwargs):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "timeout": timeout,
                **kwargs,
            }
        )
        if not self._responses:
            raise AssertionError(f"Unexpected request: {method} {url}")
        return self._responses.pop(0)


def _response(status=200, headers=None, json_data=None, text=""):
    response = mock.Mock()
    response.status_code = status
    response.headers = requests.structures.CaseInsensitiveDict(headers or {})
    response.text = text
    if json_data is None:
        response.json.side_effect = ValueError("not json")
    else:
        response.json.return_value = json_data
    return response


def _client(session, **kwargs):
    kwargs.setdefault("host", "biostar.local")
    kwargs.setdefault("port", 3002)
    kwargs.setdefault("login_id", "api")
    kwargs.setdefault("password", "secret")
    with mock.patch(f"{MODULE}.requests.Session", return_value=session):
        client = BiostarClient(**kwargs)
    return client


class TestBiostarClient(TransactionCase):
    """Client tests; the whole HTTP layer is scripted, nothing is sent."""

    def test_login_captures_header_and_logout(self):
        session = _FakeSession(
            [
                _response(headers={"be-session-id": " abc123 "}),
                _response(json_data={"Result": "ok"}),
                _response(),
            ]
        )
        client = _client(session)
        client.login()
        self.assertEqual(client._session_id, "abc123")
        client.logout()
        self.assertIsNone(client._session_id)
        self.assertEqual(session.calls[1]["method"], "GET")
        self.assertTrue(session.calls[1]["url"].endswith("/logout"))

    def test_login_falls_back_on_reply_header(self):
        session = _FakeSession(
            [
                _response(headers={"bs-ta-session-id": "tok"}),
                _response(),
            ]
        )
        client = _client(session)
        client.login()
        self.assertEqual(client._session_id, "tok")

    def test_login_falls_back_on_cookie(self):
        session = _FakeSession([_response(), _response()])
        session.cookies["bs-session-id"] = "cookiestar"
        client = _client(session)
        client.login()
        self.assertEqual(client._session_id, "cookiestar")

    def test_login_failure_raises_with_api_message(self):
        session = _FakeSession(
            [_response(status=401, json_data={"message": "Bad credentials"})]
        )
        client = _client(session)
        with self.assertRaises(BiostarAuthError) as ctx:
            client.login()
        self.assertIn("Bad credentials", str(ctx.exception))

    def test_unauthenticated_call_raises(self):
        client = _client(_FakeSession([]))
        with self.assertRaises(BiostarAuthError):
            client.list_users_page()

    def test_list_users_pages_until_total(self):
        session = _FakeSession(
            [
                _response(headers={"bs-session-id": "s1"}),
                _response(
                    json_data={
                        "status_code": "SUCCESSFUL",
                        "total": 2,
                        "records": [
                            {"user_id": "5", "name": "Ann"},
                            {"user_id": "6", "name": "Bob"},
                        ],
                    }
                ),
                _response(),
            ]
        )
        client = _client(session)
        with client:
            users = client.list_users()
        self.assertEqual([user.user_id for user in users], ["5", "6"])
        # login + single page (loop stops at total) + logout
        self.assertEqual(len(session.calls), 3)
        self.assertIsNone(client._session_id)
        logout_calls = [
            call for call in session.calls if call["url"].endswith("/logout")
        ]
        self.assertEqual(logout_calls[0]["headers"], {"bs-session-id": "s1"})

    def test_list_users_page_normalizes_dscr_roles(self):
        # Live payloads deviate from the stale swagger: roles use "dscr".
        session = _FakeSession(
            [
                _response(headers={"bs-session-id": "s"}),
                _response(
                    json_data={
                        "status_code": "SUCCESSFUL",
                        "total": 1,
                        "records": [
                            {
                                "user_id": "5",
                                "name": "Ann",
                                "roles": [
                                    {"code": "ROLE_CODE_USER", "dscr": "User Role"}
                                ],
                            }
                        ],
                    }
                ),
                _response(),
            ]
        )
        client = _client(session)
        with client:
            page = client.list_users_page(offset=0)
        self.assertEqual(page.records[0].name, "Ann")
        self.assertEqual(page.records[0].roles[0].description, "User Role")

    def test_list_users_page_validation_failure(self):
        session = _FakeSession(
            [
                _response(headers={"bs-session-id": "s"}),
                _response(json_data={"status_code": "1", "total": "total"}),
                _response(),
            ]
        )
        client = _client(session)
        with client:
            with self.assertRaises(BiostarAPIError):
                client.list_users_page(offset=0)

    def test_call_relogin_once_on_expired_session(self):
        # /users expired (401) -> transparent re-login -> retried /users.
        session = _FakeSession(
            [
                _response(headers={"bs-session-id": "expired"}),
                _response(status=401, text="Session expired"),
                _response(headers={"bs-session-id": "fresh"}),
                _response(
                    json_data={
                        "status_code": "SUCCESSFUL",
                        "total": 1,
                        "records": [{"user_id": "7", "name": "Cid"}],
                    }
                ),
                _response(),
            ]
        )
        client = _client(session)
        with client:
            users = client.list_users()
        self.assertEqual([user.user_id for user in users], ["7"])
        retry_calls = [call for call in session.calls if call["url"].endswith("/users")]
        self.assertEqual(len(retry_calls), 2)
        self.assertEqual(retry_calls[1]["headers"], {"bs-session-id": "fresh"})

    def test_report_requires_success_status(self):
        session = _FakeSession(
            [
                _response(headers={"bs-session-id": "s"}),
                _response(json_data={"status_code": "ERROR", "message": "nope"}),
                _response(),
            ]
        )
        client = _client(session)
        with client:
            with self.assertRaises(BiostarAPIError) as ctx:
                client.get_tna_report([1], "2026-10-01", "2026-10-02")
        self.assertIn("nope", str(ctx.exception))

    def test_report_pages_records_until_short_page(self):
        day_row = {
            "userId": "1",
            "hidden_dateTime": "2026/10/01",
            "inTime": "08:00:00",
            "outTime": "17:00:00",
        }
        rows = [dict(day_row, count=index) for index in range(100)]
        last = [dict(day_row, count=100)]
        session = _FakeSession(
            [
                _response(headers={"bs-session-id": "s"}),
                _response(json_data={"status_code": "SUCCESSFUL", "records": rows}),
                _response(json_data={"status_code": "SUCCESSFUL", "records": last}),
                _response(),
            ]
        )
        client = _client(session)
        with client:
            records = client.get_tna_report([1], "2026-10-01", "2026-10-02", limit=100)
        self.assertEqual(len(records), 101)
        self.assertEqual(len(session.calls), 4)  # login + 2 report pages + logout
        self.assertTrue(session.calls[1]["url"].endswith("/report.json"))
        payload = session.calls[1]["json"]
        self.assertEqual(payload["start_datetime"], "2026-10-01")
        self.assertEqual(payload["end_datetime"], "2026-10-02")
        self.assertEqual(payload["type"], "custom")
        self.assertEqual(payload["user_id_list"], ["1"])
        self.assertEqual(payload["report_type"], "REPORT_INDIVIDUAL")
        self.assertEqual(payload["report_filter_type"], "INDIVIDUAL_FILTER_DETAIL")
        self.assertTrue(payload["rebuild_time_card"])
        self.assertNotIn("language", payload)
        self.assertNotIn("group_id_list", payload)
        self.assertEqual(payload["columns"], [{"field": "username"}])

    def test_report_request_schema_validated(self):
        session = _FakeSession([_response(headers={"bs-session-id": "s"}), _response()])
        client = _client(session)
        with client:
            with self.assertRaises(BiostarAPIError):
                client.get_tna_report([1], "2026-10-01", "2026-10-02", limit=1000)
        self.assertEqual(len(session.calls), 2)  # login + logout, no report call

    def test_unreachable_server_wrapped(self):
        client = _client(_FakeSession([]))
        with mock.patch.object(
            _FakeSession,
            "request",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ):
            with self.assertRaises(BiostarAPIError):
                client.login()

    def test_base_url_has_tna_prefix(self):
        client = _client(_FakeSession([]))
        self.assertEqual(client.base_url, "https://biostar.local:3002/tna")

    def test_base_url_scheme_is_overridable(self):
        client = _client(_FakeSession([]), scheme="http")
        self.assertEqual(client.base_url, "http://biostar.local:3002/tna")
