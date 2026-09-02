import logging

from odoo import fields, models
from odoo.fields import Command, Domain

from ..schema.contact import Contact
from ..schema.product import ProductProduct
from ..services.katana_api import KatanaAPIClient
from ..services.partner_mapper import KatanaPartnerMapper
from ..services.product_mapper import KatanaProductMapper

_logger = logging.getLogger(__name__)


class ERPBackend(models.Model):
    _inherit = "erp.backend"

    backend_type = fields.Selection(
        selection_add=[("katana", "Katana")], ondelete={"katana": "cascade"}
    )

    def _sync_partners_katana(self):
        self.ensure_one()

        fetched_at = fields.Datetime.now()
        contacts: list[Contact] = KatanaAPIClient(self).fetch_all_customers(
            updated_after=self.last_sync_date
        )

        if contacts:
            Partner = self.env["res.partner"]
            mapper = KatanaPartnerMapper(self, *self._get_country_state_maps(contacts))

            existing_partners, existing_children = self._get_existing_partners(
                contacts, Partner
            )
            create_data, write_data = self._plan_reconcile(
                contacts, mapper, existing_partners, existing_children
            )
            self._apply_plan(create_data, write_data)

            _logger.info(
                "Katana: synced %s customers (%s created, %s updated)",
                len(contacts),
                len(create_data),
                len(write_data),
            )
        else:
            _logger.info("Katana: no customers to sync for backend %s", self.id)

        self.last_sync_date = fetched_at
        return True

    def _get_country_state_maps(self, contacts):
        country_codes = {a.country for c in contacts for a in c.addresses if a.country}
        state_codes = {a.state for c in contacts for a in c.addresses if a.state}

        country_map = {
            c.code: c
            for c in self.env["res.country"].search(
                [("code", "in", list(country_codes))]
            )
        }
        state_map = {
            s.code: s
            for s in self.env["res.country.state"].search(
                [("code", "in", list(state_codes))]
            )
        }
        return country_map, state_map

    def _get_existing_partners(self, contacts, Partner):
        ext_contact_ids = [contact.record_id for contact in contacts]
        all_address_ids = [
            addr.record_id for c in contacts for addr in c.addresses if addr.record_id
        ]

        backend_domain = (
            Domain("category_id", "=", self.partner_category_id.id)
            if self.partner_category_id
            else []
        )

        existing_parents = Partner.search(
            backend_domain
            + Domain("erp_external_id", "in", ext_contact_ids)
            + Domain("type", "=", "contact")
        )
        existing_partners = {
            partner.erp_external_id: partner for partner in existing_parents
        }

        existing_children = (
            Partner.search(
                [
                    ("erp_external_id", "in", all_address_ids),
                    ("parent_id", "in", existing_parents.ids),
                ]
            )
            if existing_parents
            else Partner.browse()
        )
        existing_children_dict = {
            child.erp_external_id: child for child in existing_children
        }
        return existing_partners, existing_children_dict

    def _plan_reconcile(
        self, contacts, mapper, existing_partners, existing_children_dict
    ):
        create_data: list[dict] = []
        write_data: list[tuple] = []

        for contact in contacts:
            contact_name = (
                contact.name
                or f"{contact.first_name or ''} {contact.last_name or ''}".strip()
            )
            if str(contact.record_id) not in existing_partners:
                create_data.append(mapper.build_partner_dict(contact))
            else:
                parent = existing_partners[str(contact.record_id)]
                payload = mapper.build_partner_dict(contact)
                payload["child_ids"] = self._build_child_cmds(
                    contact, contact_name, mapper, existing_children_dict
                )
                write_data.append((parent, payload))

        return create_data, write_data

    def _build_child_cmds(self, contact, contact_name, mapper, existing_children_dict):
        child_cmds = []
        for addr in contact.addresses:
            if not addr.record_id:
                continue
            addr_payload = mapper.build_address_dict(addr, contact_name, contact.email)
            child_partner = existing_children_dict.get(str(addr.record_id))
            if child_partner:
                child_cmds.append(Command.update(child_partner.record_id, addr_payload))
            else:
                child_cmds.append(Command.create(addr_payload))
        return child_cmds

    def _apply_plan(self, create_data, write_data):
        if create_data:
            self.env["res.partner"].create(create_data)
        for record, data in write_data:
            record.write(data)

    def _sync_products_katana(self):
        self.ensure_one()

        products: list[ProductProduct] = KatanaAPIClient(self).fetch_all_products()
        products = KatanaProductMapper(self).build_variant_dict(products)

        _logger.debug(products)

        ext_product_ids = [product.record_id for product in products]
        existing_external_products = self.env["erp.product"].search(
            Domain("backend_id", "=", self.id)
            + Domain("external_id", "in", ext_product_ids)
        )

        products_to_create = [
            product
            for product in products
            if product.record_id not in existing_external_products.ids
        ]

        self.env["erp.product"].create(products_to_create)

        return True
