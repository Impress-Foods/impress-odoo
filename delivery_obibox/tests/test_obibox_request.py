import logging
from datetime import datetime

from freezegun import freeze_time

from odoo.tests import tagged

from ..models import schema
from .test_delivery_common import TestDeliveryCommon

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestObiboxRequest(TestDeliveryCommon):
    def setUp(self):
        super().setUp()

    def test_make_package_1_package(self):
        package = self.env["stock.quant.package"].create({})
        package.package_type_id = self.package_type

        self.env["stock.quant"].create(
            {
                "product_id": self.productA.id,
                "quantity": 10,
                "package_id": package.id,
                "location_id": self.location.id,
                "in_date": datetime.now(),
            }
        )
        volume, long_side, weight = self.get_package_values(package)
        expected_box = schema.Box(Large=False, OverSize=False, ShipTo80=False)
        expected_dim = schema.BoxesDimensions(
            weight=weight, volume=volume, long_side=long_side
        )

        box, dim = self.sr._make_package(package)

        self.assertEqual(box, expected_box)
        self.assertEqual(dim, expected_dim)

    def test_make_package_2_packages(self):
        package_1 = self.env["stock.quant.package"].create(
            {"package_type_id": self.package_type.id}
        )
        package_2 = package_1.copy()

        self.env["stock.quant"].create(
            {
                "product_id": self.productA.id,
                "quantity": 5,
                "package_id": package_1.id,
                "location_id": self.location.id,
                "in_date": datetime.now(),
            }
        )
        self.env["stock.quant"].create(
            {
                "product_id": self.productA.id,
                "quantity": 10,
                "package_id": package_2.id,
                "location_id": self.location.id,
                "in_date": datetime.now(),
            }
        )
        packages = [package_1, package_2]

        expected_dims = []
        expected_boxes = [
            schema.Box(Large=False, OverSize=False, ShipTo80=False) for i in packages
        ]

        for package in packages:
            volume, long_side, weight = self.get_package_values(package)
            expected_dims.append(
                schema.BoxesDimensions(
                    volume=volume, weight=weight, long_side=long_side
                )
            )

        boxes = []
        dims = []
        for package in packages:
            box, dim = self.sr._make_package(package)
            boxes.append(box)
            dims.append(dim)

        self.assertEqual(boxes, expected_boxes)
        self.assertEqual(dims, expected_dims)

    def test_make_address_partner(self):
        expected_address = {
            "address1": self.partner.street,
            "address2": self.partner.street2,
            "city": self.partner.city,
            "province": self.partner.state_id.code,
            "postal_code": self.partner.zip,
        }

        address = self.sr._make_address(self.partner)
        self.assertEqual(address, expected_address)

    def test_make_address_company(self):
        partner = self.env["res.company"].browse([1])  # noqa
        expected_address = {
            "address1": partner.street,
            "address2": partner.street2 or "",
            "city": partner.city,
            "province": partner.state_id.code,
            "postal_code": partner.zip,
        }

        address = self.sr._make_address(partner)
        self.assertEqual(address, expected_address)

    def test_get_order_ref_sale_order(self):
        so = self.env["sale.order"].create(
            {"partner_id": self.env["res.partner"].browse([1]).id}
        )

        expected_name = so.name

        name = self.sr._get_order_ref(so)
        self.assertEqual(name, expected_name)

    def test_get_order_ref_picking_no_origin(self):
        picking = self.env["stock.picking"].create(
            {
                "location_id": self.location.id,
                "location_dest_id": self.location.id,
                "picking_type_id": self.out.id,
            }
        )
        expected_name = picking.name.replace("/", "")

        name = self.sr._get_order_ref(picking)
        self.assertEqual(name, expected_name)

    def test_get_order_ref_picking_origin(self):
        picking = self.env["stock.picking"].create(
            {
                "origin": "TestOrigin",
                "location_id": self.location.id,
                "location_dest_id": self.location.id,
                "picking_type_id": self.out.id,
            }
        )
        expected_name = picking.origin
        name = self.sr._get_order_ref(picking)
        self.assertEqual(name, expected_name)

    @freeze_time(datetime(year=2025, month=7, day=15))
    def test_make_shipment_request(self):
        picking = self.make_picking(n_packages=2)
        pack1 = picking.package_ids[0]
        pack2 = picking.package_ids[1]

        pack1_weight = self.package_w_uom._compute_quantity(
            pack1.shipping_weight, self.lb_uom
        )
        pack2_weight = self.package_w_uom._compute_quantity(
            pack2.shipping_weight, self.lb_uom
        )
        long_side = self.package_l_uom._compute_quantity(
            self.package_type.packaging_length, self.in_uom
        )
        volume = (
            self.package_l_uom._compute_quantity(
                self.package_type.packaging_length, self.ft_uom
            )
            ** 3
        )
        picking.date_done = datetime.today()

        total_weight = pack1_weight + pack2_weight
        boxes = [schema.Box(), schema.Box()]
        dim1 = schema.BoxesDimensions(
            weight=pack1_weight, long_side=long_side, volume=volume
        )
        dim2 = schema.BoxesDimensions(
            weight=pack2_weight, long_side=long_side, volume=volume
        )

        dims = [dim1, dim2]
        company = picking.company_id
        expected_shipping_request = schema.ShippingRequestMulti(
            order_ref_number=picking.name.replace("/", ""),
            from_address1=company.street,
            from_address2="",
            from_city=company.city,
            from_province=company.state_id.code,
            from_postal_code=company.zip,
            to_address1=self.partner.street,
            to_address2=self.partner.street2,
            to_city=self.partner.city,
            to_province=self.partner.state_id.code,
            to_postal_code=self.partner.zip,
            client_name=self.partner.name,
            name=self.partner.name,
            phone=self.partner.phone,
            email=self.partner.email,
            instructions="",
            b2b="0",
            nb_items=2,
            delivery_date_time=datetime(year=2025, month=7, day=17),
            service="NEXTDAY",
            weight=total_weight,
            boxes=boxes,
            boxes_dimensions=dims,
        )
        shipping_request = self.sr._make_shipment_request(picking)
        self.assertEqual(shipping_request, expected_shipping_request)

    def test_make_rate_request_sale_order(self):
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
            }
        )
        expected_rate_request = schema.RateRequest(
            from_postal_code=so.company_id.zip,
            to_postal_code=self.partner.zip,
            boxes=[schema.Box()],
            boxes_dimensions=[
                schema.BoxesDimensions(weight=5, volume=0.578704, long_side=10)
            ],
        )

        rate_request = self.sr._make_rate_request(so)
        self.assertEqual(rate_request, expected_rate_request)

    def test_make_rate_request_picking(self):
        picking = self.make_picking(n_packages=2)
        pack1 = picking.package_ids[0]
        pack2 = picking.package_ids[1]
        pack1_weight = self.package_w_uom._compute_quantity(
            pack1.shipping_weight, self.lb_uom
        )
        pack2_weight = self.package_w_uom._compute_quantity(
            pack2.shipping_weight, self.lb_uom
        )
        long_side = self.package_l_uom._compute_quantity(
            self.package_type.packaging_length, self.in_uom
        )
        volume = (
            self.package_l_uom._compute_quantity(
                self.package_type.packaging_length, self.ft_uom
            )
            ** 3
        )
        boxes = [schema.Box(), schema.Box()]
        dim1 = schema.BoxesDimensions(
            weight=pack1_weight, long_side=long_side, volume=volume
        )
        dim2 = schema.BoxesDimensions(
            weight=pack2_weight, long_side=long_side, volume=volume
        )

        dims = [dim1, dim2]

        expected_rate_request = schema.RateRequest(
            from_postal_code=picking.company_id.zip,
            to_postal_code=self.partner.zip,
            boxes=boxes,
            boxes_dimensions=dims,
        )
        rate_request = self.sr._make_rate_request(picking)
        self.assertEqual(rate_request, expected_rate_request)

    def test_get_pickup_date_earlier(self):
        picking_date = datetime(year=2025, month=7, day=15)
        delivery_day = "wed"
        expected_date = datetime(year=2025, month=7, day=16)
        date = self.sr._get_pickup_date(picking_date, delivery_day)
        self.assertEqual(expected_date, date)

    def test_get_pickup_date_day_of(self):
        picking_date = datetime(year=2025, month=7, day=16)
        delivery_day = "wed"
        expected_date = datetime(year=2025, month=7, day=16)
        date = self.sr._get_pickup_date(picking_date, delivery_day)
        self.assertEqual(expected_date, date)

    def test_get_pickup_date_later(self):
        picking_date = datetime(year=2025, month=7, day=17)
        delivery_day = "wed"
        expected_date = datetime(year=2025, month=7, day=23)
        date = self.sr._get_pickup_date(picking_date, delivery_day)
        self.assertEqual(expected_date, date)
