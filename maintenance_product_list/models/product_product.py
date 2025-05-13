import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    maintenance_equipment_ids = fields.Many2many(
        comodel_name="maintenance.equipment",
        string="Maintenance Equipments",
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    maintenance_equipment_ids = fields.Many2many(
        comodel_name="maintenance.equipment",
        string="Maintenance Equipments",
        compute="_compute_maintenance_equipment_ids",
        inverse="_inverse_maintenance_equipment_ids",
    )

    def _compute_maintenance_equipment_ids(self):
        self._compute_template_field_from_variant_field("maintenance_equipment_ids")

    def _inverse_maintenance_equipment_ids(self):
        self._set_product_variant_field("maintenance_equipment_ids")
