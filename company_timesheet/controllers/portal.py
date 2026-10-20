from datetime import timedelta

from odoo import http
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager

ITEMS_PER_PAGE = 50


class CompanyTimesheetPortal(CustomerPortal):
    """Lets an employee review their derived timesheet in the portal.

    A login sees its own employee's sessions plus the sessions of every
    employee in that employee's manager subtree (the same scope internal
    users get from the read rules) - letting a supervisor follow their team
    from the portal without becoming a back-office user.

    The page reuses core portal searchbar mechanics: search input, filter
    and sort dropdowns, and grouping sessions by work week (default) or by
    employee.
    """

    def _timesheet_domain(self):
        user = request.env.user
        return [
            ("employee_id", "in", user.timesheet_employee_ids.ids),
            ("company_id", "in", user.company_ids.ids),
        ]

    def _timesheet_search_domain(self, search, filterby):
        domain = self._timesheet_domain()
        if search:
            domain += [("employee_id", "ilike", search)]
        if filterby == "mine":
            own = (
                request.env["company.employee"]
                .sudo()
                .search([("partner_id", "=", request.env.user.partner_id.id)], limit=1)
            )
            domain += [("employee_id", "=", own.id)]
        elif filterby == "open":
            domain += [("check_out", "=", False)]
        return domain

    def _timesheet_searchbar_values(self, sortby, filterby, groupby, search):
        sortby = sortby if sortby in ("date", "old", "hours") else "date"
        filterby = filterby if filterby in ("all", "mine", "open") else "all"
        return {
            "sortby": sortby,
            "filterby": filterby,
            "groupby": groupby if groupby is not None else "week",
            "search": search or "",
            "searchbar_sortings": {
                "date": {"label": self.env._("Newest first"), "order": "check_in desc"},
                "old": {"label": self.env._("Oldest first"), "order": "check_in asc"},
                "hours": {
                    "label": self.env._("Longest sessions"),
                    "order": "worked_hours desc",
                },
            },
            "searchbar_filters": {
                "all": {"label": self.env._("Team")},
                "mine": {"label": self.env._("My sessions")},
                "open": {"label": self.env._("Still open")},
            },
            "searchbar_groupby": {
                "week": {"label": self.env._("Week")},
                "employee": {"label": self.env._("Employee")},
                "none": {"label": self.env._("No grouping")},
            },
            "searchbar_inputs": {
                "employee": {"input": "employee", "label": self.env._("Employee name")},
            },
            "search_in": "employee",
        }

    @staticmethod
    def _hours_label(hours):
        minutes = round(hours * 60)
        return f"{minutes // 60}:{minutes % 60:02d}"

    def _group_timesheets(self, timesheets, groupby):
        """Return display buckets in chronological order.

        Every bucket is ``{"label": str|False, "sessions": recordset,
        "hours_label": str}``; sessions never appear in two buckets.
        """
        if groupby == "none":
            return [
                {
                    "label": False,
                    "sessions": timesheets,
                    "hours_label": self._hours_label(
                        sum(timesheets.mapped("worked_hours"))
                    ),
                }
            ]
        buckets: dict = {}
        for session in timesheets:
            if groupby == "employee":
                key = session.employee_id
                label = key.name
            else:  # groupby == "week"
                start = session.date - timedelta(days=session.date.weekday())
                end = start + timedelta(days=6)
                iso_year, iso_week, _day = start.isocalendar()
                label = self.env._(
                    "Week %(week)s · %(start)s - %(end)s",
                    week=iso_week,
                    start=start.strftime("%b %d"),
                    end=end.strftime(f"%b %d {iso_year}"),
                )
                key = start
            bucket = buckets.setdefault(key, {"label": label, "sessions": []})
            bucket["sessions"].append(session)
        return [
            {
                "label": bucket["label"],
                # concat(self, *args) merges args into self: pass only the
                # siblings, otherwise the first record appears twice.
                "sessions": bucket["sessions"][0].concat(*bucket["sessions"][1:]),
                "hours_label": self._hours_label(
                    sum(session.worked_hours for session in bucket["sessions"])
                ),
            }
            for bucket in buckets.values()
        ]

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
    def portal_my_timesheets(
        self, page=1, sortby=None, filterby=None, groupby=None, search=None, **kwargs
    ):
        page = int(page)
        searchbar = self._timesheet_searchbar_values(sortby, filterby, groupby, search)
        Timesheet = request.env["company.timesheet"].sudo()
        domain = self._timesheet_search_domain(search, searchbar["filterby"])
        total = Timesheet.search_count(domain)
        pager = portal_pager(
            url="/my/timesheets",
            total=total,
            page=page,
            step=ITEMS_PER_PAGE,
            url_args={
                "sortby": searchbar["sortby"],
                "filterby": searchbar["filterby"],
                "groupby": searchbar["groupby"],
                "search": search or "",
            },
        )
        timesheets = Timesheet.search(
            domain,
            order=searchbar["searchbar_sortings"][searchbar["sortby"]]["order"],
            limit=ITEMS_PER_PAGE,
            offset=pager["offset"],
        )
        items = self._group_timesheets(timesheets, searchbar["groupby"])
        values = self._prepare_portal_layout_values()
        values.update(searchbar)
        values.update(
            {
                "timesheets": timesheets,
                "items": items,
                "page_name": "timesheet",
                "default_url": "/my/timesheets",
                "pager": pager,
            }
        )
        return request.render("company_timesheet.portal_my_timesheets", values)
