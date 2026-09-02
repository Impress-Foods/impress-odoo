from odoo.fields import Command
from odoo.tests import TransactionCase

from ..schema.contact import Address, Contact
from ..services import partner_mapper
from . import fixtures


class TestContactMapper(TransactionCase):
    @classmethod
    def setUpClass(cls):
        res = super().setUpClass()
        cls.maxDiff = None
        cls.tag = cls.env["res.partner.category"].create({"name": "Test Tag"})

        cls.backend = cls.env["erp.backend"].create(
            {
                "name": "Test",
                "backend_type": "katana",
                "partner_category_id": cls.tag.id,
            }
        )

        cls.country_map = {"us": cls.env.ref("base.us"), "ca": cls.env.ref("base.ca")}
        cls.state_map = {
            "QC": cls.env.ref("base.state_ca_qc"),
            "ON": cls.env.ref("base.state_ca_on"),
        }

        cls.mapper = partner_mapper.KatanaPartnerMapper(
            cls.backend, cls.country_map, cls.state_map
        )
        return res

    def test_build_address_dict(self):
        fixture: Address = fixtures.mock_address(
            record_id=12,
            first_name="Jane",
            last_name="Doe",
            line_1="1234 main street",
            line_2="App 1",
            city="London",
            state="ON",
            country="ca",
            zip_code="H0H 0H0",
            entity_type="shipping",
            phone="(666) 987-9874",
        )

        expected = {
            "erp_external_id": "12",
            "name": "Jane Doe",
            "email": "jane.doe@test.com",
            "category_id": [Command.link(self.tag.id)],
            "street": "1234 main street",
            "street2": "App 1",
            "city": "London",
            "state_id": self.state_map["ON"].id,
            "country_id": self.country_map["ca"].id,
            "zip": "H0H 0H0",
            "type": "delivery",
            "phone": "(666) 987-9874",
        }

        result = self.mapper.build_address_dict(
            fixture, fallback_name="Fallback Name", email="jane.doe@test.com"
        )

        self.assertDictEqual(result, expected)

    def test_build_address_dict_fallback_name(self):
        cases = [
            {"first_name": None},
            {"last_name": None},
            {"first_name": None, "last_name": None},
        ]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                fixture: Address = fixtures.mock_address(**kwargs)

                result = self.mapper.build_address_dict(
                    fixture, fallback_name="Fall McBack", email="test@test.com"
                )
                self.assertEqual(result["name"], "Fall McBack")

    def test_build_partner_dict(self):
        fixture: Contact = fixtures.mock_contact(
            record_id=12,
            name="Jane Doe",
            first_name="Jane",
            last_name="Doe",
            company="ACME Inc.",
            email="jane.doe@test.com",
            phone="(555) 123-1234",
            addresses=[
                fixtures.mock_address(
                    record_id=12,
                    first_name="Jane",
                    last_name="Doe",
                    line_1="1234 main street",
                    line_2="App 1",
                    city="London",
                    state="ON",
                    country="ca",
                    zip_code="H0H 0H0",
                    entity_type="shipping",
                    phone="(555) 123-1234",
                )
            ],
        )

        expected = {
            "erp_external_id": "12",
            "name": "Jane Doe",
            "email": "jane.doe@test.com",
            "phone": "(555) 123-1234",
            "type": "contact",
            "category_id": [Command.link(self.tag.id)],
            "child_ids": [
                Command.create(
                    {
                        "erp_external_id": "12",
                        "name": "Jane Doe",
                        "email": "jane.doe@test.com",
                        "category_id": [Command.link(self.tag.id)],
                        "street": "1234 main street",
                        "street2": "App 1",
                        "city": "London",
                        "state_id": self.state_map["ON"].id,
                        "country_id": self.country_map["ca"].id,
                        "zip": "H0H 0H0",
                        "type": "delivery",
                        "phone": "(555) 123-1234",
                    }
                )
            ],
        }

        result = self.mapper.build_partner_dict(fixture)

        self.assertDictEqual(result, expected)
