# Copyright 2011-2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

DEFAULT_MAX_RESULTS = 200
# Hard ceiling so that a public caller cannot dump the whole table in one call
MAX_RESULTS_CEILING = 5000


class ResPartner(models.Model):
    _inherit = "res.partner"

    opening_hours = fields.Char(string="Opening hours")

    AUTHORIZED_FIELDS = ["name", "city", "zip", "street", "street2", "tag"]

    @api.model
    def get_search_tags(self, search, lang):
        """Return (column, value) suggestions for the store locator search box.

        Only active, geolocated stores are considered so that every suggestion
        leads to at least one store displayed on the map.
        """
        sql = """
        WITH
            stores as (
                SELECT *
                FROM res_partner
                WHERE
                    type = 'store'
                    AND active
                    AND (
                        COALESCE(partner_latitude, 0) != 0
                        OR COALESCE(partner_longitude, 0) != 0
                    )
            ),
            names as (
                SELECT DISTINCT 'name' as column, name as value FROM stores
            ),
            cities as (
                SELECT DISTINCT 'city' as column, city as value FROM stores
            ),
            zips as (
                SELECT DISTINCT 'zip' as column, zip as value FROM stores
            ),
            streets as (
                SELECT DISTINCT 'street' as column, street as value FROM stores
                UNION
                SELECT DISTINCT 'street' as column, street2 as value FROM stores
            ),
            tags as (
                SELECT
                    DISTINCT 'tag' as column,
                    COALESCE(
                        res_partner_category.name->>%s,
                        res_partner_category.name->>'en_US'
                    ) as value
                FROM
                    res_partner_category
                    JOIN res_partner_res_partner_category_rel rel
                        ON rel.category_id = res_partner_category.id
                    JOIN stores ON stores.id = rel.partner_id
            ),
            all_tags as (
                SELECT * FROM names
                UNION SELECT * FROM cities
                UNION SELECT * FROM zips
                UNION SELECT * FROM streets
                UNION SELECT * FROM tags
            )
        SELECT * FROM all_tags WHERE value ILIKE %s;
        """
        self.env.cr.execute(sql, (lang, f"%{search}%"))
        return self.env.cr.fetchall()

    @api.model
    def _parse_max_results(self, max_results) -> int:
        """Coerce the client-supplied limit to a bounded positive integer."""
        try:
            value = int(max_results)
        except (TypeError, ValueError):
            return DEFAULT_MAX_RESULTS
        if value <= 0:
            return DEFAULT_MAX_RESULTS
        return min(value, MAX_RESULTS_CEILING)

    @api.model
    def _get_store_locator_tag_domain(self, field: str, value: str) -> Domain:
        """Translate one (field, value) search tag into a domain."""
        if field not in self.AUTHORIZED_FIELDS:
            raise ValidationError(self.env._("Unauthorized field"))
        if field == "tag":
            return Domain("category_id.name", "ilike", value)
        if field in ("street", "street2"):
            # Street suggestions come from both address lines
            return Domain("street", "ilike", value) | Domain("street2", "ilike", value)
        return Domain(field, "ilike", value)

    @api.model
    def _get_store_locator_domain(self, tags) -> Domain:
        """Active stores with coordinates, filtered by the search tags."""
        domain = Domain("type", "=", "store") & (
            Domain("partner_latitude", "!=", 0) | Domain("partner_longitude", "!=", 0)
        )
        for tag in tags or []:
            if not isinstance(tag, dict):
                raise ValidationError(self.env._("Invalid search tag"))
            domain &= self._get_store_locator_tag_domain(
                tag.get("field"), tag.get("value") or ""
            )
        return domain

    @api.model
    def _store_locator_feature(self, partner) -> dict:
        """GeoJSON feature for one store."""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [partner.partner_longitude, partner.partner_latitude],
            },
            "properties": {
                "id": partner.id,
                "name": partner.name or "",
                "zip": partner.zip or "",
                "city": partner.city or "",
                "street": partner.street or "",
                "street2": partner.street2 or "",
                "tags": partner.category_id.mapped("name"),
                "opening_hours": partner.opening_hours or "",
            },
        }

    @api.model
    def fetch_partner_geoengine(self, tags, lang, maxResults):
        domain = self._get_store_locator_domain(tags)
        max_results = self._parse_max_results(maxResults)
        partner_model = self.sudo()

        # Count first so that we never load more records than we will return
        count = partner_model.search_count(domain)
        if count > max_results:
            return {
                "error": "Too many results",
                "message": f"Too many results: {count}",
            }
        partners = partner_model.search(domain)
        return [self._store_locator_feature(partner) for partner in partners]
