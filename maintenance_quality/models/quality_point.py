import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class QualityControlPoint(models.Model):
    _inherit = "quality.point"

    equipment_ids = fields.Many2many(
        "maintenance.equipment", string="Maintenance Equipments", check_company=True
    )

    equipment_category_ids = fields.Many2many(
        "maintenance.equipment.category", string="Maintenance Equipment Categories"
    )

    workcenter_ids = fields.Many2many(
        "mrp.workcenter",
        string="Workcenters",
    )

    control_point_type = fields.Selection(
        [("stock", "Stock"), ("maintenance", "Maintenance")],
        default="stock",
    )

    picking_type_ids = fields.Many2many(
        "stock.picking.type",
        string="Operation Types",
        required=False,
        check_company=True,
    )

    check_corrective = fields.Boolean()

    check_preventive = fields.Boolean()

    @api.onchange("control_point_type")
    def _onchange_control_point_type(self):
        for record in self:
            if record.control_point_type == "maintenance":
                record.product_ids = False
                record.product_category_ids = False
                record.picking_type_ids = False

            elif self.control_point_type == "stock":
                record.equipment_ids = False
                record.equipment_category_ids = False
                record.workcenter_ids = False

            else:
                _logger.warning("In between state")
