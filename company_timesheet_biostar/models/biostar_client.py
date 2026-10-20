"""BioStar 2 T&A API client (pure Python, no Odoo imports).

This module intentionally does not import anything from ``odoo``: the client is
a plain class so it can be exercised (and mocked) without a database, and every
network side effect of the connector lives in exactly one place.

Session handling
    ``POST /tna/login`` returns the session id in a response header. The
    Suprema material disagrees about the header name depending on server
    version (``bs-session-id``, ``be-session-id``, ``bs-ta-session-id``), so
    the value is captured tolerantly and always sent back as a
    ``bs-session-id`` request header. A single transparent re-login-and-retry
    is applied on 401 so long cron runs survive session expiry.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from pydantic import ValidationError as PydanticValidationError

from ..schema.tna import ListUserItem, ReportGetInJSON, UserSearchResult

_logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 100

_SESSION_HEADERS = ("bs-session-id", "be-session-id", "bs-ta-session-id")


def _normalize_user_page(payload: dict) -> dict:
    """Map live-API drift back into the generated schema's shape.

    The published ``swagger.json`` predates the live API: role objects come
    back as ``{"code", "dscr", ...}`` where the spec declares
    ``{"code", "description"}``. Normalization lives here (never in the
    generated modules) so the schema keeps being the stable contract.
    """
    records = []
    for record in payload.get("records") or []:
        roles = [
            {
                "code": role.get("code"),
                "description": role.get("description") or role.get("dscr") or "",
            }
            for role in record.get("roles") or []
        ]
        records.append({**record, "roles": roles})
    return {**payload, "records": records}


# Proven Individual DETAIL configuration for /report.json on the target
# server: lowercase "custom" type, one minimal columns entry, id strings for
# user_id_list, and rebuild_time_card present. Int ids in the request make
# the server drop every id before building its SQL, which then fails on an
# empty ``IN ()`` clause (MSSQL error 102 seen in the field).
REPORT_INDIVIDUAL = "REPORT_INDIVIDUAL"
INDIVIDUAL_FILTER_DETAIL = "INDIVIDUAL_FILTER_DETAIL"
REPORT_REQUEST_TYPE = "custom"


class BiostarAPIError(RuntimeError):
    """Any BioStar 2 T&A communication or schema-validation failure."""


class BiostarAuthError(BiostarAPIError):
    """Login failed or the response carried no reusable session id."""


class BiostarClient:
    """Thin ``requests`` wrapper over the BioStar 2 T&A API endpoints.

    Example::

        with BiostarClient(host, port, login_id, password) as client:
            users = client.list_users()
            records = client.get_tna_report([1], "2026-10-01", "2026-10-02")
    """

    def __init__(
        self,
        host: str,
        port: int,
        login_id: str,
        password: str,
        *,
        scheme: str = "https",
        verify_ssl: bool = True,
        timeout: float = 30.0,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.login_id = login_id
        self.password = password
        self.scheme = scheme
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.session.headers["Accept"] = "application/json"
        self.session.headers["Content-Type"] = "application/json"
        self.base_url = f"{self.scheme}://{self.host}:{self.port}/tna"
        self._session_id: str | None = None

    def __enter__(self) -> BiostarClient:
        self.login()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.logout()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    def login(self) -> None:
        """Authenticate, storing the session id for later requests."""
        self._session_id = None
        response = self._http(
            "POST", "/login", json={"user_id": self.login_id, "password": self.password}
        )
        if response.status_code != 200:
            raise BiostarAuthError(
                f"Login failed ({response.status_code}): {_error_message(response)}"
            )
        self._session_id = self._extract_session_id(response)
        if not self._session_id:
            raise BiostarAuthError(
                f"Login response carries no session id ({_error_message(response)})."
            )

    def logout(self) -> None:
        """Close the BioStar session, ignoring errors on best effort."""
        if not self._session_id:
            return
        try:
            self._call("GET", "/logout")
        except Exception:  # noqa: BLE001  logout must never mask real work
            _logger.warning("BioStar logout failed (ignored).")
        finally:
            self._session_id = None

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------
    def list_users_page(
        self,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        group_id: int | None = None,
        name: str | None = None,
    ) -> UserSearchResult:
        """Fetch a single ``GET /users`` page."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if group_id is not None:
            params["group_id"] = group_id
        if name:
            params["name"] = name
        response = self._call("GET", "/users", params=params)
        payload = self._success_json(response, "GET /users")
        return self._parse(
            UserSearchResult, _normalize_user_page(payload), "GET /users"
        )

    def list_users(
        self,
        *,
        group_id: int | None = None,
        name: str | None = None,
    ) -> list[ListUserItem]:
        """Return every user, transparently walking all ``/users`` pages."""
        records: list[ListUserItem] = []
        offset = 0
        while True:
            page = self.list_users_page(offset=offset, group_id=group_id, name=name)
            records.extend(page.records)
            if not page.records or page.total is None:
                break
            offset += len(page.records)
            if offset >= page.total:
                break
        return records

    # ------------------------------------------------------------------
    # TNA report
    # ------------------------------------------------------------------
    def get_tna_report(
        self,
        user_ids: list[int],
        start_date: str,
        end_date: str,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """Return the raw ``/report.json`` records for the given user ids.

        Dates are ``YYYY-MM-DD`` strings in the BioStar server timezone.

        The body is fixed to the proven configuration (see the constants
        above): Individual DETAIL, which answers one row per interval plus a
        day roll-up row per employee. The send-time schema validation guards
        against drifting request keys; response records are plain dicts and
        the mapper owns the row semantics. Only ``user_ids`` from employee
        BioStar IDs is expected to vary between runs.
        """
        payload = {
            "limit": limit,
            "offset": 0,
            "type": REPORT_REQUEST_TYPE,
            "start_datetime": start_date,
            "end_datetime": end_date,
            "user_id_list": [str(user_id) for user_id in user_ids],
            "report_type": REPORT_INDIVIDUAL,
            "report_filter_type": INDIVIDUAL_FILTER_DETAIL,
            "rebuild_time_card": True,
            "columns": [{"field": "username"}],
        }
        self._parse(ReportGetInJSON, payload, "POST /report.json request")
        records: list[dict[str, Any]] = []
        offset = 0
        while True:
            payload["offset"] = offset
            response = self._call("POST", "/report.json", json=payload)
            page = self._parse_report(response)
            records.extend(page)
            if not page or len(page) < limit:
                break
            offset += len(page)
        return records

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _call(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Send an authenticated request, re-login once on session expiry."""
        if not self._session_id:
            raise BiostarAuthError(
                "This client is not logged in; call login()",
                " or use it as a context manager.",
            )
        response = self._http(
            method, path, headers={"bs-session-id": self._session_id}, **kwargs
        )
        if response.status_code == 401:
            _logger.info(
                "BioStar session expired; re-logging in for %s %s.", method, path
            )
            self.login()
            response = self._http(
                method, path, headers={"bs-session-id": self._session_id}, **kwargs
            )
        return response

    def _http(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = f"{self.base_url}{path}"
        try:
            return self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise BiostarAPIError(f"{method} {url} failed: {exc}") from exc

    def _extract_session_id(self, response: requests.Response) -> str | None:
        """Accept the session id from any header/cookie name in use upstream."""
        for header in _SESSION_HEADERS:
            value = response.headers.get(header)
            if value:
                return value.strip()
        for cookie in _SESSION_HEADERS:
            value = self.session.cookies.get(cookie)
            if value:
                return value
        return None

    def _success_json(self, response: requests.Response, context: str) -> Any:
        if response.status_code != 200:
            # Sequelize/DB errors carry the failing SQL in nested keys; log the
            # whole body once so support and debugging don't rely on the
            # truncated message that reaches the UI.
            _logger.warning(
                "BioStar %s failed with body: %s",
                context,
                response.text[:4000],
            )
            raise BiostarAPIError(
                f"{context} returned {response.status_code}: {_error_message(response)}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise BiostarAPIError(f"{context} returned a non-JSON body.") from exc

    def _parse(self, model: type, payload: Any, context: str) -> Any:
        try:
            return model.model_validate(payload)
        except PydanticValidationError as exc:
            raise BiostarAPIError(f"{context} failed schema validation: {exc}") from exc

    def _parse_report(self, response: requests.Response) -> list[dict[str, Any]]:
        payload = self._success_json(response, "POST /report.json")
        status = str(payload.get("status_code") or "")
        if status and status != "SUCCESSFUL":
            raise BiostarAPIError(
                f"POST /report.json failed: {payload.get('message') or status}"
            )
        records = payload.get("records") or []
        if not isinstance(records, list):
            raise BiostarAPIError(
                "POST /report.json returned a non-list records field."
            )
        return records


def _error_message(response: requests.Response) -> str:
    """Best-effort human message from a BioStar error response."""
    try:
        payload = response.json()
    except ValueError:
        return response.text[:200]
    return str(payload.get("message") or payload.get("Message") or response.text[:200])
