from odoo.exceptions import UserError
from odoo.tests import common


class TestWorksheetLogType(common.TransactionCase):
    """Tests for the worksheet.log.type model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WorksheetLogType = cls.env["worksheet.log.type"]
        cls.QualityPoint = cls.env["quality.point"]
        cls.WorksheetType = cls.env.ref("quality_control_worksheet.test_type_worksheet")

    def test_create_log_type(self):
        """Test creating a log type"""
        log_type = self.WorksheetLogType.create(
            {
                "name": "Test LOMA",
                "sequence": 10,
            }
        )
        self.assertEqual(log_type.name, "Test LOMA")

    def test_delete_unreferenced_log_type(self):
        """Test deleting a log type with no QCP references - should succeed"""
        log_type = self.WorksheetLogType.create(
            {
                "name": "Test Delete",
                "sequence": 10,
            }
        )
        log_type.unlink()
        self.assertFalse(log_type.exists())

    def test_delete_referenced_log_type_blocked(self):
        """Test deleting a log type with QCP references - should be blocked"""
        log_type = self.WorksheetLogType.create(
            {
                "name": "Test Block",
                "sequence": 10,
            }
        )
        self.QualityPoint.create(
            {
                "name": "Test QCP",
                "test_type_id": self.WorksheetType.id,
                "log_type_id": log_type.id,
            }
        )
        with self.assertRaises(UserError):
            log_type.unlink()


class TestQualityPointLogType(common.TransactionCase):
    """Tests for quality.point log_type_id feature"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WorksheetLogType = cls.env["worksheet.log.type"]
        cls.QualityPoint = cls.env["quality.point"]
        cls.WorksheetTemplate = cls.env["worksheet.template"]
        cls.WorksheetType = cls.env.ref("quality_control_worksheet.test_type_worksheet")

    def test_qcp_without_log_type(self):
        """Test QCP without log_type_id - should use direct worksheet_template_id"""
        qcp = self.QualityPoint.create(
            {
                "name": "Test QCP No Log Type",
                "test_type_id": self.WorksheetType.id,
                "worksheet_template_id": False,
            }
        )
        self.assertFalse(qcp.log_type_id)
        self.assertFalse(qcp.worksheet_template_id)

    def test_qcp_with_log_type_sync(self):
        """Test setting log_type_id on QCP syncs worksheet_template_id"""
        log_type = self.WorksheetLogType.create(
            {
                "name": "Test LOMA",
                "sequence": 10,
            }
        )
        qcp = self.QualityPoint.create(
            {
                "name": "Test QCP Sync",
                "test_type_id": self.WorksheetType.id,
                "log_type_id": log_type.id,
            }
        )
        self.assertEqual(qcp.log_type_id, log_type)
        self.assertFalse(qcp.worksheet_template_id)

        template = self.WorksheetTemplate.create(
            {
                "name": "Test Template",
                "res_model": "quality.check",
            }
        )
        log_type.active_template_id = template.id

        qcp.invalidate_recordset()
        qcp.env.flush_all()

        self.assertEqual(qcp.worksheet_template_id, template)

    def test_qcp_clearing_log_type_keeps_value(self):
        """Test clearing log_type_id keeps last worksheet_template_id value"""
        log_type = self.WorksheetLogType.create(
            {
                "name": "Test Keep",
                "sequence": 10,
            }
        )
        template = self.WorksheetTemplate.create(
            {
                "name": "Test Template Keep",
                "res_model": "quality.check",
            }
        )
        log_type.active_template_id = template.id

        qcp = self.QualityPoint.create(
            {
                "name": "Test QCP Keep",
                "test_type_id": self.WorksheetType.id,
                "log_type_id": log_type.id,
            }
        )
        self.assertEqual(qcp.worksheet_template_id, template)

        qcp.log_type_id = False
        qcp.invalidate_recordset()
        qcp.env.flush_all()

        self.assertEqual(qcp.worksheet_template_id, template)


class TestQualityCheckLogType(common.TransactionCase):
    """Tests for quality.check resolution from log type"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WorksheetLogType = cls.env["worksheet.log.type"]
        cls.QualityPoint = cls.env["quality.point"]
        cls.QualityCheck = cls.env["quality.check"]
        cls.WorksheetTemplate = cls.env["worksheet.template"]
        cls.WorksheetType = cls.env.ref("quality_control_worksheet.test_type_worksheet")

    def test_qc_from_qcp_with_log_type(self):
        """Test QC uses log type's template when QCP has log_type_id"""
        log_type = self.WorksheetLogType.create(
            {
                "name": "Test QC LOMA",
                "sequence": 10,
            }
        )
        template = self.WorksheetTemplate.create(
            {
                "name": "Test QC Template",
                "res_model": "quality.check",
            }
        )
        log_type.active_template_id = template.id

        qcp = self.QualityPoint.create(
            {
                "name": "Test QC QCP",
                "test_type_id": self.WorksheetType.id,
                "log_type_id": log_type.id,
            }
        )

        qc = self.QualityCheck.create(
            {
                "point_id": qcp.id,
                "production_id": False,
            }
        )

        self.assertEqual(qc.worksheet_template_id, template)

    def test_qc_from_qcp_without_log_type(self):
        """Test QC direct template when QCP has no log_type_id (backwards compat)"""
        template = self.WorksheetTemplate.create(
            {
                "name": "Test QC Template Direct",
                "res_model": "quality.check",
            }
        )

        qcp = self.QualityPoint.create(
            {
                "name": "Test QC QCP Direct",
                "test_type_id": self.WorksheetType.id,
                "worksheet_template_id": template.id,
            }
        )

        qc = self.QualityCheck.create(
            {
                "point_id": qcp.id,
                "production_id": False,
            }
        )

        self.assertEqual(qc.worksheet_template_id, template)

    def test_qc_new_gets_new_template_after_change(self):
        """Test changing log type's template affects NEW QC checks"""
        log_type = self.WorksheetLogType.create(
            {
                "name": "Test New Template",
                "sequence": 10,
            }
        )
        template_v1 = self.WorksheetTemplate.create(
            {
                "name": "Template v1",
                "res_model": "quality.check",
            }
        )
        template_v2 = self.WorksheetTemplate.create(
            {
                "name": "Template v2",
                "res_model": "quality.check",
            }
        )
        log_type.active_template_id = template_v1.id

        qcp = self.QualityPoint.create(
            {
                "name": "Test QCP Template Change",
                "test_type_id": self.WorksheetType.id,
                "log_type_id": log_type.id,
            }
        )

        qc_v1 = self.QualityCheck.create(
            {
                "point_id": qcp.id,
                "production_id": False,
            }
        )
        self.assertEqual(qc_v1.worksheet_template_id, template_v1)

        log_type.active_template_id = template_v2.id
        qc_v1.env.flush_all()

        qc_v2 = self.QualityCheck.create(
            {
                "point_id": qcp.id,
                "production_id": False,
            }
        )
        self.assertEqual(qc_v2.worksheet_template_id, template_v2)


class TestBackwardsCompatibility(common.TransactionCase):
    """Tests for backwards compatibility"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.QualityPoint = cls.env["quality.point"]
        cls.QualityCheck = cls.env["quality.check"]
        cls.WorksheetTemplate = cls.env["worksheet.template"]
        cls.WorksheetType = cls.env.ref("quality_control_worksheet.test_type_worksheet")

    def test_existing_qcp_without_log_type(self):
        """Test existing QCP without log_type_id works as before"""
        template = self.WorksheetTemplate.create(
            {
                "name": "Existing Template",
                "res_model": "quality.check",
            }
        )

        qcp = self.QualityPoint.create(
            {
                "name": "Existing QCP",
                "test_type_id": self.WorksheetType.id,
                "worksheet_template_id": template.id,
            }
        )

        self.assertFalse(qcp.log_type_id)
        self.assertEqual(qcp.worksheet_template_id, template)

    def test_existing_qc_keeps_frozen_template(self):
        """Test existing QC keeps frozen template reference"""
        template = self.WorksheetTemplate.create(
            {
                "name": "Frozen Template",
                "res_model": "quality.check",
            }
        )

        qcp = self.QualityPoint.create(
            {
                "name": "Frozen QCP",
                "test_type_id": self.WorksheetType.id,
                "worksheet_template_id": template.id,
            }
        )

        qc = self.QualityCheck.create(
            {
                "point_id": qcp.id,
                "production_id": False,
            }
        )
        self.assertEqual(qc.worksheet_template_id, template)

        qcp.worksheet_template_id = False
        qcp.env.flush_all()

        self.assertEqual(qc.worksheet_template_id, template)
