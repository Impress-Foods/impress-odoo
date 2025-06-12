from odoo.tests.common import TransactionCase, tagged


@tagged("impress")
class TestMaintenanceRequestSequence(TransactionCase):
    def setUp(self):
        super().setUp()
        self.MaintenanceRequest = self.env["maintenance.request"]

    def test_sequence_is_set_on_create(self):
        request = self.MaintenanceRequest.create(
            {
                "name": "Test Request",
            }
        )
        self.assertTrue(request.sequence)
        self.assertNotEqual(request.sequence, "New")
        self.assertIn(request.sequence, request.display_name)

    def test_display_name_with_sequence(self):
        request = self.MaintenanceRequest.create(
            {
                "name": "Test Request 3",
            }
        )
        request.sequence = "MRQ0001"
        request._compute_display_name()
        self.assertEqual(request.display_name, f"{request.sequence} - {request.name}")
