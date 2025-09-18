from odoo.tests import common


class TestQualityLogs(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.LogLine = cls.env["log_line.mixin"]
        cls.QualityCheck = cls.env["quality.check"]
        cls.Production = cls.env["mrp.production"]
        cls.Product = cls.env["product.product"]
        cls.Lot = cls.env["stock.lot"]
