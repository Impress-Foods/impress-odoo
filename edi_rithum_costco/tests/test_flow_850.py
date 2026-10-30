"""Inbound 850 flow: a purchase order creates a sale order, and bad input is refused."""

from datetime import datetime

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.edi_x12.x12 import outbound
from odoo.addons.edi_x12.x12.simple_xml import Loop, Segment

from .maps import MAP_PATH

SENDER = "COSTCOTEST00001"
SCHEME = "X12"


def _order_text(
    po_number="PO-7741",
    vendor_sku="999999",
    ship_to=True,
    ship_to_country="US",
    ship_to_state="AK",
    packing_language="",
    quantity="2",
) -> str:
    nodes = [
        Segment(
            "BEG",
            {"BEG01": "00", "BEG02": "SA", "BEG03": po_number, "BEG05": "20200310"},
        ),
        Segment("REF", {"REF01": "IA", "REF02": "3286495"}),
        Segment(
            "TD5",
            {
                "TD501": "Z",
                "TD502": "ZZ",
                "TD503": "UPS",
                "TD504": "ZZ",
                "TD505": "Ground",
            },
        ),
    ]
    if packing_language:
        nodes.insert(2, Segment("REF", {"REF01": "PK", "REF03": packing_language}))
    if ship_to:
        nodes.append(
            Loop(
                "N1_LOOP",
                [
                    Segment(
                        "N1",
                        {"N101": "ST", "N102": "SHIP TO", "N103": "ZZ", "N104": "0001"},
                    ),
                    Segment("N3", {"N301": "1 MAIN ST"}),
                    Segment(
                        "N4",
                        {
                            "N401": "ANYTOWN",
                            "N402": ship_to_state,
                            "N403": "99501",
                            "N404": ship_to_country,
                        },
                    ),
                ],
            )
        )
    nodes.append(
        Loop(
            "PO1_LOOP",
            [
                Segment(
                    "PO1",
                    {
                        "PO101": "0001",
                        "PO102": quantity,
                        "PO103": "EA",
                        "PO104": "5.5",
                        "PO106": "SK",
                        "PO107": "COSTCO-1",
                        "PO108": "VN",
                        "PO109": vendor_sku,
                    },
                )
            ],
        )
    )
    nodes.append(Segment("CTT", {"CTT01": "1"}))
    envelope = outbound.Envelope(
        sender_id=SENDER,
        receiver_id="OURID",
        control_number=7,
        production=False,
        sent_at=datetime(2020, 3, 10, 9, 0),
        interchange_version="00401",
        functional_version="004010",
        functional_id="PO",
    )
    return outbound.render(
        outbound.interchange(envelope, Loop("BODY", nodes), "850", "0001"), MAP_PATH
    )


class TestFlow850(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mapping = cls.env["edi.rithum.costco.mapping.850"]
        scheme = cls.env.ref("edi_x12.id_category_x12")
        cls.partner = cls.env["res.partner"].create({"name": "Retail Customer"})
        cls.env["res.partner.id_number"].create(
            {"partner_id": cls.partner.id, "category_id": scheme.id, "name": SENDER}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Widget", "default_code": "999999"}
        )
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.unit.unece_code = "C62"

    def test_order_is_created_with_lines_and_ship_to(self):
        (order,) = self.mapping.create_orders(_order_text(), SCHEME, MAP_PATH)
        self.assertEqual(order.partner_id, self.partner)
        self.assertEqual(order.client_order_ref, "PO-7741")
        (line,) = order.order_line
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.product_uom_id, self.unit)
        self.assertEqual(line.product_uom_qty, 2)
        self.assertEqual(line.price_unit, 5.5)
        self.assertEqual(line.edi_id, "0001")
        self.assertEqual(line.costco_sku, "COSTCO-1")
        self.assertEqual(order.costco_shipping_method, "Ground")

    def test_ship_to_becomes_a_delivery_contact_of_the_customer(self):
        (order,) = self.mapping.create_orders(
            _order_text(po_number="PO-SHIP"), SCHEME, MAP_PATH
        )
        shipping = order.partner_shipping_id
        self.assertEqual(shipping.parent_id, self.partner)
        self.assertEqual(shipping.type, "delivery")
        self.assertEqual(
            (shipping.street, shipping.zip, shipping.country_id.code),
            ("1 MAIN ST", "99501", "US"),
        )

    def test_order_without_ship_to_is_accepted(self):
        # The heading N1 loop is M/U (Costco's requirement), not X12 M, so the map
        # accepts a PO without it. The order then ships to the customer's address.
        orders = self.mapping.create_orders(
            _order_text(po_number="PO-NOSHIP", ship_to=False), SCHEME, MAP_PATH
        )
        self.assertEqual(orders.partner_shipping_id, orders.partner_id)

    def test_same_po_twice_is_refused(self):
        self.mapping.create_orders(_order_text(po_number="PO-DUP"), SCHEME, MAP_PATH)
        with self.assertRaises(UserError):
            self.mapping.create_orders(
                _order_text(po_number="PO-DUP"), SCHEME, MAP_PATH
            )

    def test_unknown_product_is_refused(self):
        with self.assertRaises(UserError):
            self.mapping.create_orders(
                _order_text(po_number="PO-SKU", vendor_sku="000000"), SCHEME, MAP_PATH
            )

    def test_line_without_vendor_item_number_is_refused(self):
        # PO109 is required in the packing slip, so a line without it is not matched.
        text = _order_text(po_number="PO-NOVN").replace("*VN*999999", "")
        with self.assertRaises(UserError):
            self.mapping.create_orders(text, SCHEME, MAP_PATH)

    def test_unknown_sender_is_refused(self):
        with self.assertRaises(UserError):
            self.mapping.create_orders(
                _order_text(po_number="PO-SENDER"), "OTHER", MAP_PATH
            )

    def test_invalid_document_is_refused(self):
        with self.assertRaises(UserError):
            self.mapping.create_orders("ISA*garbage~", SCHEME, MAP_PATH)

    def _shipping(self, **kwargs):
        text = _order_text(**kwargs)
        return self.mapping.create_orders(text, SCHEME, MAP_PATH).partner_shipping_id

    def test_the_contact_gets_the_packing_slip_language(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        shipping = self._shipping(po_number="PO-FR", packing_language="FR")
        self.assertEqual(shipping.lang, "fr_CA")

    def test_english_falls_back_to_an_installed_english_language(self):
        shipping = self._shipping(po_number="PO-EN", packing_language="EN")
        self.assertTrue(shipping.lang.startswith("en_"))

    def test_no_language_in_the_file_leaves_the_contact_language_empty(self):
        shipping = self._shipping(po_number="PO-NOLANG")
        self.assertFalse(shipping.lang)

    def test_a_language_that_is_not_installed_is_reported_not_guessed(self):
        self.env["res.lang"].search([("code", "like", "fr_")]).active = False
        shipping = self._shipping(po_number="PO-NOFR", packing_language="FR")
        self.assertFalse(shipping.lang)
        order = self.env["sale.order"].search([("client_order_ref", "=", "PO-NOFR")])
        self.assertIn(
            "no installed language", " ".join(order.message_ids.mapped("body"))
        )

    def test_a_ship_to_without_country_takes_the_customers(self):
        canada = self.env.ref("base.ca")
        self.partner.country_id = canada
        shipping = self._shipping(
            po_number="PO-CA", ship_to_country="", ship_to_state="QC"
        )
        self.assertEqual(shipping.country_id, canada)
        self.assertEqual(shipping.state_id.code, "QC")

    def test_a_ship_to_without_country_stays_without_one_if_the_customer_has_none(
        self,
    ):
        shipping = self._shipping(po_number="PO-NOCTRY", ship_to_country="")
        self.assertFalse(shipping.country_id)
        self.assertFalse(shipping.state_id)

    def test_the_new_fields_are_on_the_sale_order_form(self):
        arch = self.env["sale.order"].get_view(view_type="form")["arch"]
        self.assertIn('name="costco_shipping_method"', arch)
        self.assertIn('name="costco_sku"', arch)
