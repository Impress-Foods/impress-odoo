from odoo.addons.component.core import AbstractComponent


class ErpConnectorComponent(AbstractComponent):
    """Common base for every ERP connector component.

    It intentionally has no ``_collection``: it is generic and applies to
    any ERP backend, so a single implementation is shared by all ERPs.
    """

    _name = "erp.connector"
    _inherit = ["base.connector"]
    _description = "ERP Connector Component"
