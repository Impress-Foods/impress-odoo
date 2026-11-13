"""The migration to 19.0.1.1.0 gives existing orders their retailer."""

import importlib.util

from odoo.tools import file_path

from .common import CostcoShipmentCase


class TestMigration(CostcoShipmentCase):
    def test_orders_get_the_retailer_of_the_file_they_came_from(self):
        order, __ = self._order(kits=3)
        partner = order.rithum_partner_id
        self.assertTrue(partner)
        order.rithum_partner_id = False
        path = file_path("edi_rithum_costco/migrations/19.0.1.1.0/post-migration.py")
        spec = importlib.util.spec_from_file_location("post_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.env.flush_all()
        module.migrate(self.env.cr, "19.0.1.0.0")
        order.invalidate_recordset()
        self.assertEqual(order.rithum_partner_id, partner)
