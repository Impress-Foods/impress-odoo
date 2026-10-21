from odoo import models


class ErpPickingBinding(models.AbstractModel):
    """Shared glue for ERP delivery/picking bindings.

    Concrete picking bindings (one per ERP) inherit this model, declare
    ``_inherits = {"stock.picking": "odoo_id"}``, the ``odoo_id`` and
    ``backend_id`` fields, and the ``UNIQUE(backend_id, external_id)``
    constraint.
    """

    _name = "erp.picking.binding"
    _inherit = ["erp.binding.mixin"]
    _description = "ERP Picking Binding"

    def _erp_picking(self):
        """Return the ``stock.picking`` record behind this binding."""
        self.ensure_one()
        return self.odoo_id
