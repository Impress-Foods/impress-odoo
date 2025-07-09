import json
import logging
from datetime import datetime
from unittest.mock import patch

from freezegun import freeze_time

from odoo.tests import common, tagged

from ..models import schema
from ..models.obibox_request import ObiboxProvider

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestObiboxRequest(common.TransactionCase):
    def setUp(self):
        super().setUp()

        self.sr = ObiboxProvider(
            None, prod_environment=False, username="test", token="test"
        )

        location_id = self.ref("stock.stock_location_stock")
        self.location = self.env["stock.location"].browse(location_id)
        self.partner_location = self.env["stock.location"].browse(
            self.ref("stock.stock_location_customers")
        )
        delivery_product = self.env["product.product"].create(
            {
                "name": "Delivery Product",
                "type": "service",
            }
        )

        self.obibox_method = self.env["delivery.carrier"].create(
            {
                "name": "Obibox",
                "delivery_type": "obibox",
                "integration_level": "rate_and_ship",
                "product_id": delivery_product.id,
                "obibox_api_key": "test_api_key",
                "obibox_username": "test_username",
                "obibox_label_format": "zpl",
            }
        )

        self.package_type = self.env["stock.package.type"].create(
            {
                "name": "Test Package Type",
                "base_weight": 0.1,
                "height": 254,
                "packaging_length": 254,
                "width": 254,
            }
        )

        self.productA = self.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "product",
                "weight": 0.1,
            }
        )
        self.productB = self.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "product",
                "weight": 0.1,
            }
        )
        self.out = self.env["stock.picking.type"].browse(
            self.ref("stock.picking_type_out")
        )

        uom = self.env["uom.uom"]
        self.in_uom = uom.browse(self.ref("uom.product_uom_inch"))
        self.ft_uom = uom.browse(self.ref("uom.product_uom_foot"))
        self.lb_uom = uom.browse(self.ref("uom.product_uom_lb"))
        self.package_w_uom = uom.search(
            [("name", "=", self.package_type.weight_uom_name)]
        )[0]

        self.package_l_uom = uom.search(
            [("name", "=", self.package_type.length_uom_name)]
        )[0]

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Client",
                "street": "1010 avenue test",
                "street2": "App 1010",
                "city": "TestVille",
                "state_id": self.env["res.country.state"]
                .search([("code", "=", "QC")])[0]
                .id,
                "zip": "H0H0H0",
                "phone": "4181234567",
                "email": "test@test.com",
            }
        )

    def get_package_values(self, package):
        package_l = self.package_l_uom._compute_quantity(
            self.package_type.packaging_length, self.in_uom
        )
        package_h = self.package_l_uom._compute_quantity(
            self.package_type.height, self.in_uom
        )
        package_w = self.package_l_uom._compute_quantity(
            self.package_type.width, self.in_uom
        )

        package_l_ft = self.package_l_uom._compute_quantity(
            self.package_type.packaging_length, self.ft_uom
        )
        package_h_ft = self.package_l_uom._compute_quantity(
            self.package_type.height, self.ft_uom
        )
        package_w_ft = self.package_l_uom._compute_quantity(
            self.package_type.width, self.ft_uom
        )

        volume = package_l_ft * package_h_ft * package_w_ft
        long_side = max(package_l, package_h, package_w)
        weight = self.package_w_uom._compute_quantity(
            package.shipping_weight, self.lb_uom
        )
        return volume, long_side, weight

    def make_picking(self, n_packages=1):
        picking = self.env["stock.picking"].create(
            {
                "location_id": self.location.id,
                "location_dest_id": self.partner_location.id,
                "picking_type_id": self.out.id,
                "partner_id": self.partner.id,
                "carrier_id": self.obibox_method.id,
            }
        )
        self.env["stock.quant"].create(
            {
                "product_id": self.productA.id,
                "quantity": 10,
                "location_id": self.location.id,
                "in_date": datetime.now(),
            }
        )
        self.env["stock.quant"].create(
            {
                "product_id": self.productB.id,
                "quantity": 10,
                "location_id": self.location.id,
                "in_date": datetime.now(),
            }
        )
        self.env["stock.move"].create(
            {
                "location_dest_id": self.partner_location.id,
                "location_id": self.location.id,
                "name": "Test Move",
                "product_id": self.productA.id,
                "product_uom": self.productA.uom_id.id,
                "product_uom_qty": 10,
                "picking_id": picking.id,
            }
        )
        if n_packages > 1:
            self.env["stock.move"].create(
                {
                    "location_dest_id": self.partner_location.id,
                    "location_id": self.location.id,
                    "name": "Test Move",
                    "product_id": self.productB.id,
                    "product_uom": self.productB.uom_id.id,
                    "product_uom_qty": 10,
                    "picking_id": picking.id,
                }
            )

        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(len(picking.move_ids_without_package), n_packages)

        smlA = picking.move_line_ids.filtered(lambda ml: ml.product_id == self.productA)
        smlA.write({"quantity": 10.0, "picked": True})
        quantA = smlA.quant_id

        pack1 = self.env["stock.quant.package"].create(
            {"package_type_id": self.package_type.id, "quant_ids": [quantA.id]}
        )
        smlA.result_package_id = pack1.id

        self.assertEqual(len(picking.package_ids), 1)
        if n_packages > 1:
            smlB = picking.move_line_ids.filtered(
                lambda ml: ml.product_id == self.productB
            )
            smlB.quantity = 10
            smlB.picked = True
            quantB = smlB.quant_id
            pack2 = self.env["stock.quant.package"].create(
                {"package_type_id": self.package_type.id, "quant_ids": [quantB.id]}
            )
            smlB.result_package_id = pack2.id
            self.assertEqual(len(picking.package_ids), 2)
        return picking

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
            delivery_date_time=datetime(year=2025, month=7, day=16),
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

    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    def test_get_rate_order(self, mock_api):
        mock_api.return_value = json.loads(
            """[{"ServiceName": "NEXTDAY",
            "PickupETA": "2025-07-09T11:00:00-04:00",
            "DeliveryETA": "2025-07-10T07:00:00-04:00",
            "PriceInCAD": 8.66
        }
        ]"""
        )

        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
            }
        )
        expected_response = {
            "success": True,
            "price": 8.66,
            "error_message": False,
            "warning_message": False,
        }
        response = self.sr.get_rate(so)
        self.assertEqual(expected_response, response)

    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    def test_full_get_rate_so(self, mock_api):
        mock_api.return_value = json.loads(
            """[{"ServiceName": "NEXTDAY",
            "PickupETA": "2025-07-09T11:00:00-04:00",
            "DeliveryETA": "2025-07-10T07:00:00-04:00",
            "PriceInCAD": 8.66
        }
        ]"""
        )

        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
            }
        )
        wizard_action = so.action_open_delivery_wizard()
        wizard = (
            self.env["choose.delivery.carrier"]
            .with_context(**wizard_action["context"])
            .create({"carrier_id": self.obibox_method.id})
        )
        wizard.update_price()
        wizard.button_confirm()

        self.assertEqual(len(so.order_line), 1)
        self.assertEqual(so.order_line[0].product_id, self.obibox_method.product_id)
        self.assertEqual(so.order_line[0].price_subtotal, 8.66)

    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    @freeze_time(datetime(year=2025, month=7, day=15))
    def test_complete_book_shipment_1_package(self, mock_api):
        return_value_1 = json.loads(
            """[{"ServiceName": "NEXTDAY",
            "PickupETA": "2025-07-09T11:00:00-04:00",
            "DeliveryETA": "2025-07-10T07:00:00-04:00",
            "PriceInCAD": 8.66
        }
        ]"""
        )
        return_value_2 = json.loads(
            """[{"Hub": "QUE", "RouteCode":"T-202",
            "TrackingNumber":"trackingNo", "Waybill":"LabelData" }]"""
        )

        mock_api.side_effect = [return_value_1, return_value_2]

        picking = self.make_picking()

        picking.button_validate()
        self.assertEqual("trackingNo", picking.carrier_tracking_ref)
        self.assertEqual("trackingNo", picking.obibox_tracking_numbers)

    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    @freeze_time(datetime(year=2025, month=7, day=15))
    def test_complete_book_shipment_2_package(self, mock_api):
        return_value_1 = json.loads(
            """[{"ServiceName": "NEXTDAY",
            "PickupETA": "2025-07-09T11:00:00-04:00",
            "DeliveryETA": "2025-07-10T07:00:00-04:00",
            "PriceInCAD": 8.66
        }
        ]"""
        )
        return_value_2 = json.loads(
            """[{"Hub": "QUE", "RouteCode":"T-202",
            "TrackingNumber":"trackingNo", "Waybill":"LabelData" }, {
            "Hub": "QUE", "RouteCode":"T-202",
            "TrackingNumber":"trackingNo2", "Waybill":"LabelData" }]"""
        )

        mock_api.side_effect = [return_value_1, return_value_2]

        picking = self.make_picking(n_packages=2)

        picking.button_validate()
        self.assertEqual("trackingNo", picking.carrier_tracking_ref)
        self.assertEqual("trackingNo,trackingNo2", picking.obibox_tracking_numbers)
        self.assertTrue(picking.shipping_label_attachment_id)  # type: ignore

    @patch(
        "odoo.addons.delivery_obibox.models.obibox_request.ObiboxProvider._make_api_request"
    )
    def test_cancel_shipment(self, mock_api):
        return_value_1 = json.loads(
            """[{"ServiceName": "NEXTDAY",
            "PickupETA": "2025-07-09T11:00:00-04:00",
            "DeliveryETA": "2025-07-10T07:00:00-04:00",
            "PriceInCAD": 8.66
        }
        ]"""
        )
        return_value_2 = json.loads(
            """[{"Hub": "QUE", "RouteCode":"T-202",
            "TrackingNumber":"trackingNo", "Waybill":"LabelData" }, {
            "Hub": "QUE", "RouteCode":"T-202",
            "TrackingNumber":"trackingNo2", "Waybill":"LabelData" }]"""
        )
        return_value_3 = True
        mock_api.side_effect = [
            return_value_1,
            return_value_2,
            return_value_3,
            return_value_3,  # twice since we have to cancel 2 packages
        ]

        picking = self.make_picking()
        picking.button_validate()
        picking.cancel_shipment()
        self.assertFalse(picking.carrier_tracking_ref)
        self.assertFalse(picking.shipping_label_attachment_id)  # type: ignore
