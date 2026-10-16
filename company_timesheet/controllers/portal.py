from odoo import http
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager

ITEMS_PER_PAGE = 50


class CompanyTimesheetPortal(CustomerPortal):
    """Lets an employee review their own derived timesheet in the portal."""

    def _timesheet_domain(self):
        return [("employee_id.partner_id", "=", request.env.user.partner_id.id)]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "timesheet_count" in counters:
            values["timesheet_count"] = (
                request.env["company.timesheet"]
                .sudo()
                .search_count(self._timesheet_domain())
            )
        return values

    @http.route(
        ["/my/timesheets", "/my/timesheets/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_timesheets(self, page=1, **kwargs):
        Timesheet = request.env["company.timesheet"].sudo()
        domain = self._timesheet_domain()
        total = Timesheet.search_count(domain)
        pager = portal_pager(
            url="/my/timesheets",
            total=total,
            page=page,
            step=ITEMS_PER_PAGE,
        )
        timesheets = Timesheet.search(
            domain,
            order="check_in desc",
            limit=ITEMS_PER_PAGE,
            offset=pager["offset"],
        )
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "timesheets": timesheets,
                "page_name": "timesheet",
                "default_url": "/my/timesheets",
                "pager": pager,
            }
        )
        return request.render("company_timesheet.portal_my_timesheets", values)
