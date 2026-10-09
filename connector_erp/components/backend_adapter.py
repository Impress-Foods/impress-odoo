from odoo.addons.component.core import AbstractComponent


class ErpBackendAdapter(AbstractComponent):
    """Base adapter that speaks to an ERP API.

    Concrete adapters implement ``read_record`` (and, when needed,
    ``search_records``) for one external entity, and are applied on the
    matching binding model.

    The methods deliberately avoid the Odoo ORM names (``read``, ``create``,
    ``write``) so that ``pylint-odoo``'s ``method-required-super`` check,
    which is name-based and assumes ORM model overrides, does not raise a
    false positive on adapters.
    """

    _name = "erp.backend.adapter"
    _inherit = ["base.backend.adapter", "erp.connector"]
    _description = "ERP Backend Adapter"

    def read_record(self, external_id, **kwargs):
        """Read one external record and return its raw data."""
        raise NotImplementedError
