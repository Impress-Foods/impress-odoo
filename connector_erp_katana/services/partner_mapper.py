from odoo.fields import Command

from ..schema.contact import Address, Contact

TYPE_MAP = {"billing": "invoice", "shipping": "delivery"}


class KatanaPartnerMapper:
    def __init__(self, backend, country_map, state_map):
        self.backend = backend
        self.country_map = country_map
        self.state_map = state_map

    def build_address_dict(self, addr: Address, fallback_name, email):
        """Katana customer_address -> Odoo partner"""
        addr_name = (
            f"{addr.first_name or ''} {addr.last_name or ''}".strip()
            if addr.first_name and addr.last_name
            else fallback_name
        )

        state_id = self.state_map.get(addr.state, False)
        country_id = self.country_map.get(addr.country, False)
        return {
            "erp_external_id": str(addr.record_id),
            "name": addr_name or fallback_name,
            "category_id": [Command.link(self.backend.partner_category_id.id)],
            "email": email,
            "street": addr.line_1,
            "street2": addr.line_2,
            "city": addr.city,
            "state_id": state_id.id if state_id else False,
            "zip": addr.zip_code,
            "country_id": country_id.id if country_id else False,
            "type": TYPE_MAP.get(addr.entity_type, "other"),
            "phone": addr.phone,
        }

    def build_partner_dict(self, contact: Contact) -> dict:
        """Katana customer -> Odoo partner"""
        contact_name = (
            contact.name
            or f"{contact.first_name or ''} {contact.last_name or ''}".strip()
        )

        return {
            "erp_external_id": str(contact.record_id),
            "name": contact_name,
            "email": contact.email,
            "phone": contact.phone,
            "type": "contact",
            "category_id": [Command.link(self.backend.partner_category_id.id)],
            "child_ids": [
                Command.create(
                    self.build_address_dict(addr, contact_name, contact.email)
                )
                for addr in contact.addresses
                if addr.record_id
            ],
        }
