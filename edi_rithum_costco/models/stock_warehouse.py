from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    costco_warehouse_code = fields.Char(
        string="Costco warehouse ID",
        help="The ID of this warehouse as registered for Costco in the Rithum "
        "portal. Costco needs it on every shipment confirmation (N104 of the "
        "warehouse name segment) and rejects the confirmation if it does not know "
        "it. It must also match the warehouse IDs of the inventory file.",
    )
