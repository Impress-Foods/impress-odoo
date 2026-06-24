import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    maintenance_equipment_ids = fields.Many2many(
        comodel_name="maintenance.equipment",
        string="Maintenance Equipments",
    )
    vendor_code = fields.Char(compute="_compute_vendor_code", store=True)
    current_vendor_code = fields.Char(compute="_compute_current_vendor_code")

    @api.depends("seller_ids", "seller_ids.product_code")
    def _compute_vendor_code(self):
        for product in self:
            if len(product.seller_ids) > 0:
                vendor = product.seller_ids.sorted("sequence")[0]
                product.vendor_code = vendor.product_code
            else:
                product.vendor_code = False

    def _compute_current_vendor_code(self):
        order_id = self.env["purchase.order"].browse(
            self.env.context.get("product_catalog_order_id", False)
        )
        for record in self:
            if order_id:
                supplier_ids = record.seller_ids.filtered_domain(
                    [("partner_id", "=", order_id.partner_id.id)]
                ).sorted("sequence")

                if supplier_ids:
                    record.current_vendor_code = supplier_ids[0].product_code
                else:
                    record.current_vendor_code = False
            else:
                record.current_vendor_code = False


class ProductTemplate(models.Model):
    _inherit = "product.template"

    maintenance_equipment_ids = fields.Many2many(
        comodel_name="maintenance.equipment",
        string="Maintenance Equipments",
        compute="_compute_maintenance_equipment_ids",
        inverse="_inverse_maintenance_equipment_ids",
    )

    vendor_code = fields.Char(compute="_compute_vendor_code", store=True)

    def _compute_maintenance_equipment_ids(self):
        self._compute_template_field_from_variant_field("maintenance_equipment_ids")

    def _inverse_maintenance_equipment_ids(self):
        self._set_product_variant_field("maintenance_equipment_ids")

    @api.depends("product_variant_ids", "product_variant_ids.vendor_code")
    def _compute_vendor_code(self):
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.vendor_code = template.product_variant_ids[0].vendor_code
            else:
                template.vendor_code = False
