import logging
from datetime import datetime, timedelta

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestStockLot(TransactionCase):
    def setUp(self):
        super().setUp()
        self.product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "detailed_type": "product",
                "tracking": "lot",
                "use_expiration_date": True,
                "expiration_time": 20,
                "use_time": 10,
                "removal_time": 2,
                "alert_time": 5,
                "default_code": "EXXXXX",
            }
        )

    def test_create_lot(self):
        date = datetime.strptime("2025-01-01", "%Y-%m-%d")
        lot = self.env["stock.lot"].create(
            {"name": "25001", "product_id": self.product.id}
        )

        exp_date = date + timedelta(days=self.product.expiration_time + 1)
        best_before_date = exp_date - timedelta(days=self.product.use_time)
        removal_date = exp_date - timedelta(days=self.product.removal_time + 1)
        alert_date = exp_date - timedelta(days=self.product.alert_time + 1)

        lot._calculate_expiration_date()

        self.assertEqual(lot.expiration_date.date(), exp_date.date())
        self.assertEqual(lot.use_date.date(), best_before_date.date())
        self.assertEqual(lot.removal_date.date(), removal_date.date())
        self.assertEqual(lot.alert_date.date(), alert_date.date())

    def test_get_lots_to_send_alert(self):
        # 03-06-2010 + 15 = 18-06-2010
        lot_before = self.env["stock.lot"].create(
            {"name": "10154", "product_id": self.product.id}
        )
        lot_before._calculate_expiration_date()

        # 04-06-2010 + 15 = 19-06-2010
        lot_on_with_quant = self.env["stock.lot"].create(
            {"name": "10155", "product_id": self.product.id}
        )
        lot_on_with_quant._calculate_expiration_date()

        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "quantity": 10,
                "lot_id": lot_on_with_quant.id,
                "location_id": self.env.ref("stock.stock_location_stock").id,  # type: ignore
            }
        )

        lot_on_wo_quant = self.env["stock.lot"].create(
            {"name": "10155-1", "product_id": self.product.id}
        )
        lot_on_wo_quant._calculate_expiration_date()
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "quantity": 0,
                "lot_id": lot_on_wo_quant.id,
                "location_id": self.env.ref("stock.stock_location_stock").id,  # type: ignore
            }
        )

        # 05-06-2010 + 15 = 20-06-2010
        lot_after = self.env["stock.lot"].create(
            {"name": "10156", "product_id": self.product.id}
        )
        lot_after._calculate_expiration_date()

        lots = self.env["stock.lot"]._get_lots_to_send_alert(
            datetime(year=2010, month=6, day=19).date()
        )

        self.assertEqual(1, len(lots))
        self.assertEqual(lot_on_with_quant.id, lots[0].id)
