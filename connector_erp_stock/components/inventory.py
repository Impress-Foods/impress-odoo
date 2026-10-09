from odoo.addons.component.core import AbstractComponent


class ErpInventorySynchronizer(AbstractComponent):
    """Base synchronizer for inventory.

    Inventory has no per-record external identity, so it is a synchronizer
    rather than a binding: concrete implementations read levels from the
    backend and apply them to stock.
    """

    _name = "erp.inventory.synchronizer"
    _inherit = ["base.synchronizer", "erp.connector"]
    _description = "ERP Inventory Synchronizer"
    _usage = "inventory.synchronizer"

    def run(self, **kwargs):
        raise NotImplementedError
