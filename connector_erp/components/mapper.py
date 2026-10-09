from odoo.addons.component.core import AbstractComponent


class ErpImportMapper(AbstractComponent):
    """Base mapper turning external data into Odoo values."""

    _name = "erp.import.mapper"
    _inherit = ["base.import.mapper", "erp.connector"]
    _description = "ERP Import Mapper"
