import logging
from collections import OrderedDict
from operator import itemgetter

from odoo import http
from odoo.http import request
from odoo.tools import groupby as groupbyelem

from odoo.addons.portal.controllers import portal
from odoo.addons.portal.controllers.portal import pager as portal_pager

_logger = logging.getLogger(__name__)


class CustomerPortal(portal.CustomerPortal):
    @http.route(
        ["/my/manufacturings", "/my/manufacturings/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_manufacturings(
        self,
        **kwargs,
    ):
        values = self._prepare_manufacturings_values(**kwargs)

        return http.request.render(
            "impress_production_billing.portal_my_manufacturings", values
        )

    def _get_searchbar_filters(self):
        searchbar_filters = {
            "all": {"label": self.env._("All"), "domain": []},
            "done": {"label": self.env._("Done"), "domain": [("state", "=", "done")]},
            "confirmed": {
                "label": self.env._("Confirmed"),
                "domain": [("state", "=", "confirmed")],
            },
        }
        return searchbar_filters

    def _get_searchbar_groupby(self):
        searchbar_groupby = {
            "none": {"input": "none", "label": self.env._("None")},
            "product": {"input": "product", "label": self.env._("Product")},
            "purchase_order": {
                "input": "purchase_order",
                "label": self.env._("Purchase Order"),
            },
            "state": {"input": "state", "label": self.env._("Status")},
        }
        return searchbar_groupby

    def _get_searchbar_sortings(self):
        searchbar_sortings = {
            "date": {
                "label": self.env._("Newest"),
                "order": "create_date desc, id desc",
            },
            "name": {"label": self.env._("Name"), "order": "name asc, id asc"},
        }
        return searchbar_sortings

    def _get_searchbar_inputs(self, search=""):
        searchbar_inputs = {
            "all": {
                "label": self.env._("Search in All"),
                "input": "all",
                "domain": [],
            },
            "name": {
                "label": self.env._("Search in Name"),
                "input": "name",
                "domain": [("name", "ilike", search)],
            },
            "product": {
                "label": self.env._("Search in Product"),
                "input": "product",
                "domain": [
                    "|",
                    "|",
                    ("product_id.default_code", "ilike", search),
                    ("product_id.name", "ilike", search),
                    ("product_id.barcode", "ilike", search),
                ],
            },
            "purchase_order": {
                "label": self.env._("Search in Purchase Order"),
                "input": "purchase_order",
                "domain": [("billing_sale_order_ref", "ilike", search)],
            },
            "lot": {
                "label": self.env._("Search in Lot"),
                "input": "lot",
                "domain": [("lot_id.name", "ilike", search)],
            },
        }
        return searchbar_inputs

    def _production_get_groupby_mapping(self):
        return {
            "product": "product_id",
            "purchase_order": "billing_sale_order_id",
            "state": "state",
        }

    def _prepare_manufacturings_values(
        self,
        page=1,
        date_begin=None,
        date_end=None,
        sortby="date",
        filterby="all",
        groupby="none",
        product=None,
        so=None,
        search="",
        search_in="all",
        **kwargs,
    ):
        ProductionOrder = request.env["mrp.production"]

        values = self._prepare_portal_layout_values()

        commercial_partner = request.env.user.partner_id.commercial_partner_id
        SaleOrder = request.env["sale.order"]

        searchbar_filters = self._get_searchbar_filters()
        searchbar_groupby = self._get_searchbar_groupby()
        searchbar_sortings = self._get_searchbar_sortings()
        searchbar_inputs = self._get_searchbar_inputs(search=search)

        domain = searchbar_filters[filterby]["domain"]  # type: ignore

        # If no SO is specified, get all SOs for the user
        if so is None:
            so_domain = [("partner_id", "=", commercial_partner.id)]
            so_ids = [so.id for so in SaleOrder.search(so_domain)]
            domain += [("billing_sale_order_id.partner_id", "=", commercial_partner.id)]
        else:
            # If SO is specified, cast the SO id to an int and make it the search domain
            so_ids = [int(so)]
            domain += [("billing_sale_order_id", "in", so_ids)]

        if product is not None:
            product_domain = [("product_id", "=", int(product))]
            domain += product_domain

        if search != "":
            domain += searchbar_inputs[search_in]["domain"]  # type: ignore

        order = searchbar_sortings[sortby]["order"]  # type: ignore

        # Default sort by value
        if not sortby or sortby not in searchbar_sortings:
            sortby = "date"

        order = searchbar_sortings[sortby]["order"]

        count = ProductionOrder.search_count(domain)

        # Allows to persist the state of filters across pagination
        url_args = {"search_in": search_in}
        if date_begin is not None:
            url_args["date_begin"] = date_begin
        if date_end is not None:
            url_args["date_end"] = date_end
        if filterby != "all":
            url_args["filterby"] = filterby
        if groupby != "none":
            url_args["groupby"] = groupby
        if sortby != "date":
            url_args["sortby"] = sortby
        if search != "":
            url_args["search"] = search

        pager = portal_pager(
            url="/my/manufacturings",
            url_args=url_args,
            total=count,
            page=page,
            step=self._items_per_page,
        )
        mo_ids = ProductionOrder.search(
            domain, order=order, limit=self._items_per_page, offset=pager["offset"]
        )

        def get_grouped_manufacturings(pager_offset):
            productions = ProductionOrder.search(
                domain, order=order, limit=self._items_per_page, offset=pager_offset
            )

            groupby_mapping = self._production_get_groupby_mapping()
            group = groupby_mapping.get(groupby)  # type: ignore
            if group:
                grouped_productions = [
                    ProductionOrder.concat(*g)
                    for k, g in groupbyelem(productions, itemgetter(group))
                ]
            else:
                grouped_productions = [productions] if productions else []

            production_states = dict(
                ProductionOrder._fields["state"]._description_selection(request.env)  # type: ignore
            )
            if sortby == "status":
                if groupby == "none" and grouped_productions:
                    grouped_productions[0] = grouped_productions[0].sorted(
                        lambda productions: production_states.get(productions[0].state)
                    )
                else:
                    grouped_productions.sort(
                        key=lambda productions: production_states.get(
                            productions[0].state
                        )  # type: ignore
                    )  # type: ignore
            return grouped_productions

        values.update(
            {
                "date": date_begin,
                "manufacturings": mo_ids,
                "grouped_productions": get_grouped_manufacturings,
                "page_name": "manufacturing",
                "pager": pager,
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
                "searchbar_filters": OrderedDict(sorted(searchbar_filters.items())),
                "filterby": filterby,
                "searchbar_groupby": searchbar_groupby,
                "groupby": groupby,
                "default_url": "/my/manufacturings",
                "search": search,
                "search_in": search_in,
                "searchbar_inputs": searchbar_inputs,
            }
        )
        return values
