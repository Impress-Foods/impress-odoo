"""Inbound 850: each purchase order in an interchange becomes a sale order."""

from datetime import datetime, time

from odoo import api, models
from odoo.exceptions import UserError
from odoo.fields import Command

from odoo.addons.base.models.res_country import ResCountry
from odoo.addons.base.models.res_partner import ResPartner
from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord
from odoo.addons.edi_x12.x12 import simple_xml
from odoo.addons.edi_x12.x12.party import Party
from odoo.addons.edi_x12.x12.reading import isa_sender, isa_usage_indicator
from odoo.addons.sale.models.sale_order import SaleOrder

from ..documents import tset_850
from ..documents.tset_850 import OrderLine, PurchaseOrder

# X12 unit codes -> UNECE codes, the key `uom.uom.unece_code` is matched on.
UNECE_UNIT = {"EA": "C62"}
VENDOR_IDENTIFIER = "VN"  # PO108 qualifier: PO109 is the seller's item number
# Packing slip language (REF*PK) -> installed languages, best first.
PREFERRED_LANGUAGES = {"EN": ("en_CA", "en_US"), "FR": ("fr_CA", "fr_FR")}


TEST_INDICATOR = "T"
PRODUCTION_INDICATOR = "P"


class EdiRithumCostcoMapping850(models.AbstractModel):
    """Builds sale orders from validated Costco 850 documents.

    Matching goes through the helpers of ``base_business_document_import``. The
    sale order is created here, not through ``sale.order.import``, which is a
    transient wizard built for a user screen.
    """

    _name = "edi.rithum.costco.mapping.850"
    _description = "Costco 850 to Sale Order"

    @api.model
    def process(self, exchange_record: EDIExchangeRecord) -> None:
        """Create the sale orders of an inbound 850 and link them to the record."""
        backend = exchange_record.backend_id
        orders = self.create_orders(
            exchange_record._get_file_content(),
            backend.x12_partner_scheme,
            exchange_record.rithum_partner_id.map_path(),
            production=backend.x12_production,
            exchange_record=exchange_record,
        )
        exchange_record._set_related_record(orders)
        self.env["edi.rithum.costco.product"].bind_order_lines(
            backend, orders.order_line
        )

    def create_orders(
        self,
        text: str,
        partner_scheme: str,
        map_path: str,
        production: bool = False,
        exchange_record: EDIExchangeRecord | None = None,
    ) -> SaleOrder:
        """Create one sale order per 850 in the interchange."""
        exchange_record = exchange_record or self.env["edi.exchange.record"]
        outcome = self.env["edi.exchange.type"].x12_validate(text, map_path)
        self._check_environment(text, production)
        __, sender_id = isa_sender(text)
        partner = self._partner(sender_id, partner_scheme)
        purchase_orders = tset_850.read_purchase_orders(simple_xml.parse(outcome.xml))
        orders = self.env["sale.order"]
        for purchase_order in purchase_orders:
            orders |= self._create_order(purchase_order, partner, exchange_record)
        return orders

    def _check_environment(self, text: str, production: bool) -> None:
        """Refuse test traffic on production, and production traffic on test."""
        expected = PRODUCTION_INDICATOR if production else TEST_INDICATOR
        found = isa_usage_indicator(text)
        if found != expected:
            raise UserError(
                self.env._(
                    "ISA15 is '%(found)s' but this backend expects '%(expected)s'.",
                    found=found,
                    expected=expected,
                )
            )

    def _partner(self, sender: str, partner_scheme: str) -> ResPartner:
        """The customer identified by the interchange sender."""
        partner_dict = {"id_number": [{"schemeID": partner_scheme, "value": sender}]}
        return self.env["business.document.import"]._match_partner(
            partner_dict, [], partner_type="customer"
        )

    def _create_order(
        self,
        purchase_order: PurchaseOrder,
        partner: ResPartner,
        exchange_record: EDIExchangeRecord,
    ) -> SaleOrder:
        chatter: list[str] = []
        self._check_not_duplicate(partner, purchase_order.po_number)
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "partner_shipping_id": self._shipping_partner(
                    purchase_order.ship_to,
                    partner,
                    chatter,
                    purchase_order.packing_slip_language,
                ).id,
                "costco_shipping_method": purchase_order.shipping_method,
                "client_order_ref": purchase_order.po_number,
                "date_order": datetime.combine(purchase_order.created_on, time()),
                "origin_exchange_record_id": exchange_record.id,
                "order_line": [
                    Command.create(self._order_line_vals(line, chatter))
                    for line in purchase_order.lines
                ],
            }
        )
        self.env["business.document.import"].post_create_or_update(
            {"chatter_msg": chatter}, order
        )
        return order

    def _check_not_duplicate(self, partner: ResPartner, po_number: str) -> None:
        """Refuse a second order for the same PO, so a resent 850 is not duplicated."""
        existing = self.env["sale.order"].search(
            [
                ("client_order_ref", "=", po_number),
                ("partner_id", "child_of", partner.commercial_partner_id.id),
                ("state", "!=", "cancel"),
            ],
            limit=1,
        )
        if existing:
            raise UserError(
                self.env._(
                    "PO %(po)s already exists as %(order)s.",
                    po=po_number,
                    order=existing.name,
                )
            )

    def _shipping_partner(
        self,
        ship_to: Party | None,
        partner: ResPartner,
        chatter: list[str],
        language: str = "",
    ) -> ResPartner:
        """The ship-to from N1*ST, matched or created under the customer."""
        if ship_to is None:
            return partner
        country = self._ship_to_country(ship_to, partner)
        shipping_dict = {
            "name": ship_to.name,
            "street": ship_to.address,
            "city": ship_to.city,
            "zip": ship_to.postal_code,
            "state_code": ship_to.state,
            "country_code": country.code or "",
        }
        shipping = self.env["business.document.import"]._match_shipping_partner(
            shipping_dict, partner, chatter, raise_exception=False
        )
        return shipping or self._create_shipping_partner(
            ship_to, partner, country, language, chatter
        )

    def _ship_to_country(self, ship_to: Party, partner: ResPartner) -> ResCountry:
        """The ship-to country, or the customer's when the file leaves it out."""
        country = self.env["res.country"]
        if ship_to.country:
            country = country.search([("code", "=", ship_to.country)], limit=1)
        return country or partner.country_id

    def _create_shipping_partner(
        self,
        ship_to: Party,
        partner: ResPartner,
        country: ResCountry,
        language: str,
        chatter: list[str],
    ) -> ResPartner:
        state = self.env["res.country.state"]
        if country:
            state = state.search(
                [("code", "=", ship_to.state), ("country_id", "=", country.id)],
                limit=1,
            )
        return self.env["res.partner"].create(
            {
                "parent_id": partner.id,
                "type": "delivery",
                "name": ship_to.name,
                "street": ship_to.address,
                "city": ship_to.city,
                "zip": ship_to.postal_code,
                "state_id": state.id,
                "country_id": country.id,
                "lang": self._language(language, chatter),
            }
        )

    def _language(self, code: str, chatter: list[str]) -> str | bool:
        """The installed language for a packing slip language code (EN or FR)."""
        code = code.upper()
        if not code:
            return False
        installed = [lang for lang, _name in self.env["res.lang"].get_installed()]
        matching = [lang for lang in installed if lang.startswith(code.lower() + "_")]
        for lang in PREFERRED_LANGUAGES.get(code, ()):
            if lang in matching:
                return lang
        if matching:
            return min(matching)
        chatter.append(
            self.env._(
                "The packing slip language %(code)s has no installed language, so "
                "the delivery contact has none set.",
                code=code,
            )
        )
        return False

    def _order_line_vals(self, line: OrderLine, chatter: list[str]) -> dict:
        bdio = self.env["business.document.import"]
        product = bdio._match_product(self._product_dict(line), chatter, seller=False)
        uom = bdio._match_uom(
            {"unece_code": self._unece_unit(line.unit)}, chatter, product
        )
        if not uom:
            raise UserError(
                self.env._(
                    "No unit of measure has UNECE code %(code)s.",
                    code=self._unece_unit(line.unit),
                )
            )
        vals = {
            "product_id": product.id,
            "product_uom_id": uom.id,
            "product_uom_qty": float(line.quantity),
            "price_unit": float(line.unit_price),
            "edi_id": line.line_number,
            "costco_sku": line.sku,
        }
        if line.description:
            # The partner's own wording, accents included, is kept on the line.
            vals["name"] = line.description
        return vals

    def _product_dict(self, line: OrderLine) -> dict:
        """Our item number (PO109, VN), not Costco's SKU (PO107, SK)."""
        vendor_sku = line.identifiers.get(VENDOR_IDENTIFIER)
        if not vendor_sku:
            raise UserError(
                self.env._(
                    "PO1 line %(line)s has no vendor item number (PO109, VN).",
                    line=line.line_number,
                )
            )
        return {"code": vendor_sku}

    def _unece_unit(self, unit: str) -> str:
        if unit not in UNECE_UNIT:
            raise UserError(
                self.env._("Unit %(unit)s has no UNECE mapping.", unit=unit)
            )
        return UNECE_UNIT[unit]
