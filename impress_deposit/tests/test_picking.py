from odoo.fields import Command

from odoo.addons.stock.models.stock_picking import StockPicking

from .test_common import TestCommon


class TestStockPicking(TestCommon):
    def test_delivery_containers_w_deposit(self) -> None:
        QTY = 10
        picking: StockPicking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.delivery_type.id,
                "partner_id": self.partner_w_deposit.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product_w_deposit.id,
                            "product_uom_qty": QTY,
                            "location_id": self.wh.lot_stock_id.id,
                            "location_dest_id": self.wh.lot_stock_id.id,
                        }
                    )
                ],
            }
        )

        self.assertEqual(picking.container_qty, 0)
        picking.action_confirm()
        picking.action_assign()
        picking.button_validate()
        self.assertEqual(picking.container_qty, QTY)

    def test_delivery_containers_wo_deposit(self) -> None:
        QTY = 10
        picking: StockPicking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.delivery_type.id,
                "partner_id": self.partner_wo_deposit.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product_w_deposit.id,
                            "product_uom_qty": QTY,
                            "location_id": self.wh.lot_stock_id.id,
                            "location_dest_id": self.wh.lot_stock_id.id,
                        }
                    )
                ],
            }
        )

        self.assertEqual(picking.container_qty, 0)
        picking.action_confirm()
        picking.action_assign()
        picking.button_validate()
        self.assertEqual(picking.container_qty, 0)
