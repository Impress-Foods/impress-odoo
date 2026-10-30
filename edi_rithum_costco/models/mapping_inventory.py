"""Outbound 846: the stock of the products bound to Costco, per warehouse."""

import math

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.edi_core_oca.models.edi_backend import EDIBackend
from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord
from odoo.addons.edi_x12.x12 import outbound
from odoo.addons.product.models.product_product import ProductProduct
from odoo.addons.stock.models.stock_warehouse import StockWarehouse

from ..documents import tset_846

FUNCTIONAL_ID = "IB"
MERCHANT = "COSTCO"
REPORT_NUMBER_FORMAT = "%Y%m%d%H%M%S"


class EdiRithumCostcoMappingInventory(models.AbstractModel):
    _name = "edi.rithum.costco.mapping.inventory"
    _description = "Costco 846 Inventory"

    @api.model
    def generate(self, exchange_record: EDIExchangeRecord) -> str:
        """The inventory advice of the products bound to the record's backend."""
        backend = exchange_record.backend_id
        now = fields.Datetime.now()
        advice = tset_846.InventoryAdvice(
            report_number=now.strftime(REPORT_NUMBER_FORMAT),
            created_on=now.date(),
            merchant=MERCHANT,
            items=tuple(self._items(backend)),
        )
        body = tset_846.build_body(advice)
        tree = outbound.interchange(self._envelope(), body, tset_846.TSET, "0001")
        return outbound.render(tree, exchange_record.type_id.x12_map_path())

    def _envelope(self) -> outbound.Envelope:
        """Addressed to Costco, from the identity set for it: nothing here answers."""
        partner = self.env.ref("edi_rithum_costco.rithum_partner_costco")
        return partner.x12_envelope(FUNCTIONAL_ID)

    def _items(self, backend: EDIBackend) -> list[tset_846.InventoryItem]:
        bindings = self.env["edi.rithum.costco.product"].search(
            [("backend_id", "=", backend.id)]
        )
        if not bindings:
            raise UserError(
                self.env._("No product is bound to %(name)s.", name=backend.name)
            )
        warehouses = self.env["stock.warehouse"].search(
            [("costco_warehouse_code", "!=", False)]
        )
        if not warehouses:
            raise UserError(
                self.env._("Set the Costco warehouse ID on at least one warehouse.")
            )
        quantities = self._available(bindings.product_id, warehouses)
        return [
            tset_846.InventoryItem(
                vendor_sku=binding.product_id.default_code or "",
                buyer_sku=binding.costco_sku,
                description=binding.product_id.name or "",
                stock=tuple(
                    tset_846.WarehouseStock(
                        warehouse.costco_warehouse_code,
                        quantities[warehouse, binding.product_id],
                    )
                    for warehouse in warehouses
                ),
                discontinued_on=binding.discontinued_on,
            )
            for binding in bindings
        ]

    def _available(self, products: ProductProduct, warehouses: StockWarehouse) -> dict:
        """Whole units free to sell, per (warehouse, product); kits count whole kits.

        free_qty is on hand minus what is reserved. With a warehouse in the
        context it covers that warehouse only, and for a kit it follows from the
        components (mrp extends the computation).
        """
        quantities = {}
        for warehouse in warehouses:
            scoped = products.with_context(warehouse_id=warehouse.id)
            for product, free in zip(products, scoped.mapped("free_qty"), strict=True):
                quantities[warehouse, product] = max(0, math.floor(free))
        return quantities
