from .test_delivery_common import TestDeliveryCommon


class TestGetPackages(TestDeliveryCommon):
    @classmethod
    def setUpClass(self):
        super().setUpClass()

    def test_get_packages_single_package(self):
        """_get_packages returns the single package linked to a non-done picking"""
        picking = self.make_picking()
        packages = picking._get_packages()
        self.assertEqual(len(packages), 1)

    def test_get_packages_multiple_packages(self):
        """_get_packages returns all packages when picking has multiple"""
        picking = self.make_picking(n_packages=2)
        packages = picking._get_packages()
        self.assertEqual(len(packages), 2)

    def test_get_packages_no_packages(self):
        """_get_packages returns empty recordset when no packages exist"""
        picking = self.env["stock.picking"].create(
            {
                "location_id": self.location.id,
                "location_dest_id": self.partner_location.id,
                "picking_type_id": self.out.id,
                "partner_id": self.partner.id,
            }
        )
        packages = picking._get_packages()
        self.assertEqual(len(packages), 0)

    def test_get_packages_picking_done(self):
        """_get_packages searches stock.package.history when picking is done"""
        picking = self.make_picking()
        packages_before = picking._get_packages()
        self.assertEqual(len(packages_before), 1)

        picking.button_validate()
        self.assertEqual(picking.state, "done")

        packages_after = picking._get_packages()
        self.assertEqual(len(packages_after), 1)

    def test_get_packages_done_with_multiple_packages(self):
        """_get_packages returns all packages after validation with multiple packages"""
        picking = self.make_picking(n_packages=2)
        self.assertEqual(len(picking._get_packages()), 2)

        picking.button_validate()
        self.assertEqual(picking.state, "done")

        packages = picking._get_packages()
        self.assertEqual(len(packages), 2)

    def test_get_packages_non_done_creates_no_history(self):
        """_get_packages uses stock.package directly before picking is done"""
        picking = self.make_picking()
        packages = picking._get_packages()
        self.assertEqual(len(packages), 1)

        # stock.package.history should have no records for non-done pickings
        domain = [("picking_ids", "in", picking.ids)]
        history = self.env["stock.package.history"].search(domain)
        self.assertEqual(len(history), 0)
