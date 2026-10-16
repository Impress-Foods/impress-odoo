from odoo import models


class ErpProductBinding(models.AbstractModel):
    """Shared glue for ERP product bindings.

    Concrete product bindings (one per ERP) inherit this model, declare
    ``_inherits = {"product.product": "odoo_id"}``, the ``odoo_id`` and
    ``backend_id`` fields, and the ``UNIQUE(backend_id, external_id)``
    constraint.
    """

    _name = "erp.product.binding"
    _inherit = ["erp.binding.mixin"]
    _description = "ERP Product Binding"

    def _erp_product(self):
        """Return the ``product.product`` record behind this binding."""
        self.ensure_one()
        return self.odoo_id
