import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    maintenance_equipment_ids = fields.Many2many(
        comodel_name="maintenance.equipment",
        string="Maintenance Equipments",
    )
    vendor_code = fields.Char(compute="_compute_vendor_code")

    def _compute_vendor_code(self):
        for product in self:
            if len(product.seller_ids) > 0:
                vendor = product.seller_ids.sorted("sequence")[0]
                product.vendor_code = vendor.product_code
            else:
                product.vendor_code = False


class ProductTemplate(models.Model):
    _inherit = "product.template"

    maintenance_equipment_ids = fields.Many2many(
        comodel_name="maintenance.equipment",
        string="Maintenance Equipments",
        compute="_compute_maintenance_equipment_ids",
        inverse="_inverse_maintenance_equipment_ids",
    )
    vendor_code = fields.Char(compute="_compute_vendor_code")

    def _compute_maintenance_equipment_ids(self):
        self._compute_template_field_from_variant_field("maintenance_equipment_ids")

    def _inverse_maintenance_equipment_ids(self):
        self._set_product_variant_field("maintenance_equipment_ids")

    def _compute_vendor_code(self):
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.vendor_code = template.product_variant_ids[0].vendor_code
            else:
                template.vendor_code = False
