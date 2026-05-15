from odoo.upgrade import util


def migrate(cr, version):
    util.rename_field(
        cr, "stock.scrap", "maintenance_equipement_id", "maintenance_equipment_id"
    )
