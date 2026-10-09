from odoo.addons.component.core import Component


class ErpBinder(Component):
    """Default binder resolving the external <-> Odoo identity.

    It is generic: with no ``_collection`` and no ``_apply_on``, it is the
    fallback binder for every ERP binding. A backend that needs a different
    identity rule (extra fields, custom unwrap) declares its own binder with
    ``_apply_on``/``_collection`` and the framework prefers it.

    The field names below match ``erp.binding.mixin`` and the framework's
    ``base.binder`` defaults.
    """

    _name = "erp.binder"
    _inherit = ["base.binder", "erp.connector"]
    _description = "ERP Binder"
    _usage = "binder"

    _external_field = "external_id"
    _backend_field = "backend_id"
    _odoo_field = "odoo_id"
    _sync_date_field = "sync_date"
