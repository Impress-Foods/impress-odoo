import logging

import requests

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

ANNOUNCE_URL_PARAM = "impress.ip_announce.url"
ANNOUNCE_TOKEN_PARAM = "impress.ip_announce.token"
ANNOUNCE_TIMEOUT = 5


class IPChangeController(http.Controller):
    @http.route("/_odoo.sh/ip-change", auth="public")
    def ip_change(self, old=None, new=None):
        _logger.info("IP address changed from %s to %s", old, new)
        self._announce_ip_change(old, new)
        return "ok"

    def _announce_ip_change(self, old, new):
        # sudo(): system parameters are admin-only, but this route is public.
        params = request.env["ir.config_parameter"].sudo()
        url = params.get_param(ANNOUNCE_URL_PARAM)
        if not url:
            return
        token = params.get_param(ANNOUNCE_TOKEN_PARAM)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            response = requests.post(
                url,
                json={"ip": new},
                headers=headers,
                timeout=ANNOUNCE_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException:
            # Log and continue so Odoo.sh always gets 'ok'.
            _logger.exception("Failed to announce IP change from %s to %s", old, new)
