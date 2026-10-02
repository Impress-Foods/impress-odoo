from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase, mute_logger


class TestPrintingLabelFormat(TransactionCase):
    def _make_report(self, name, report_type, size="2x4"):
        return self.env["ir.actions.report"].create(
            {
                "name": name,
                "model": "product.product",
                "report_type": report_type,
                "label_size_id": self._size(size).id if size else False,
                "report_name": "base.report_partner",
            }
        )

    def _make_printer(self, name, label_format=False, size="2x4"):
        return self.env["printing.printer"].create(
            {
                "name": name,
                "system_name": name.lower().replace(" ", "-"),
                "backend": "base",
                "label_format": label_format,
                "label_size_id": self._size(size).id if size else False,
            }
        )

    def _size(self, name):
        return self.env.ref(f"printing_label_format.size_{name}")

    def test_a_transport_report_type_has_no_qweb_renderer(self):
        """A type a transport owns renders its own document, so it must not be
        sent to a QWeb renderer it does not have."""
        report = self._make_report("PLF HTML Report", "qweb-html")

        self.assertIsNone(report._label_renderer_name())

    def test_the_payload_is_keyed_by_target_and_counts_labels(self):
        # A base model on purpose: this module depends on the printing stack
        # only, so the target has to be one a test database is guaranteed to
        # carry.
        report = self._make_report("PLF Payload Label", "qweb-text")
        target = self.env["res.partner"].create({"name": "PLF Payload Partner"})

        self.assertEqual(
            report._print_label_data(target, copies=3),
            {str(target.id): {"label_count": 3}},
        )
        # A zero quantity is omitted rather than encoded as zero.
        self.assertEqual(
            report._print_label_data(target, copies=2),
            {str(target.id): {"label_count": 2}},
        )

    def test_the_report_declares_its_format(self):
        pdf_report = self._make_report("PLF PDF Label", "qweb-pdf")
        zpl_report = self._make_report("PLF ZPL Label", "qweb-text")

        self.assertEqual(pdf_report.label_format, "pdf")
        self.assertEqual(zpl_report.label_format, "zpl")

    def test_a_printer_takes_one_format_and_size(self):
        """A template written for one size is not printable on another, so both
        halves have to match, not just the format."""
        report = self._make_report("PLF 2x4 Label", "qweb-text", size="2x4")
        same = self._make_printer("PLF 2x4", "zpl", size="2x4")
        other_size = self._make_printer("PLF 4x6", "zpl", size="4x6")
        other_format = self._make_printer("PLF PDF 2x4", "pdf", size="2x4")

        self.assertTrue(same._supports_report(report))
        self.assertFalse(other_size._supports_report(report))
        self.assertFalse(other_format._supports_report(report))

    def test_a_printer_takes_one_format_only(self):
        pdf_report = self._make_report("PLF PDF Label", "qweb-pdf")
        zpl_report = self._make_report("PLF ZPL Label", "qweb-text")
        pdf = self._make_printer("PLF PDF", "pdf")
        zpl = self._make_printer("PLF ZPL", "zpl")

        self.assertTrue(pdf._supports_report(pdf_report))
        self.assertFalse(pdf._supports_report(zpl_report))
        self.assertTrue(zpl._supports_report(zpl_report))
        self.assertFalse(zpl._supports_report(pdf_report))

    def test_a_report_type_outside_the_map_matches_nothing(self):
        # The map used to fall back on ZPL for anything that was not a PDF.
        # An unmapped type has to resolve to no format, so it is offered to no
        # printer, instead of being handed to the ZPL ones.
        html_report = self._make_report("PLF HTML Label", "qweb-html")
        zpl_printer = self._make_printer("PLF ZPL", "zpl")

        self.assertFalse(html_report.label_format)
        self.assertFalse(zpl_printer._supports_report(html_report))

    def test_the_map_is_where_routing_lives(self):
        # Extending the map is all it takes to route a report type to a format
        # that is already declared, so a module adding a format only has to
        # list it in the selection and map it here.
        report_model = self.env["ir.actions.report"]
        html_report = self._make_report("PLF HTML Label", "qweb-html")
        zpl_printer = self._make_printer("PLF ZPL", "zpl")
        pdf_printer = self._make_printer("PLF PDF", "pdf")

        with patch.object(
            type(report_model),
            "_label_format_map",
            return_value={"qweb-pdf": "pdf", "qweb-text": "zpl", "qweb-html": "pdf"},
        ):
            html_report._compute_label_format()
            self.assertEqual(html_report.label_format, "pdf")
            self.assertTrue(pdf_printer._supports_report(html_report))
            self.assertFalse(zpl_printer._supports_report(html_report))

    def test_an_undeclared_printer_takes_no_report(self):
        # The field stays optional so this module can be installed on a
        # database that already has printers. An undeclared printer must
        # therefore support nothing, so it is never offered for a label.
        undeclared = self.env["printing.printer"].create(
            {"name": "PLF No Format", "system_name": "plf-no-format"}
        )
        pdf_report = self._make_report("PLF PDF Label", "qweb-pdf")
        zpl_report = self._make_report("PLF ZPL Label", "qweb-text")

        self.assertFalse(undeclared.label_format)
        self.assertFalse(undeclared._supports_report(pdf_report))
        self.assertFalse(undeclared._supports_report(zpl_report))

    def test_the_report_size_is_edited_here(self):
        """The size is declared in this module, so its editor ships here too.

        Only the printer side used to have a view, so a database with this
        module but not the dashboard could declare a report size it had no way
        to edit.
        """
        view = self.env.ref("printing_label_format.ir_actions_report_view_form")

        self.assertEqual(view.model, "ir.actions.report")
        self.assertIn("label_size", view.arch)

    def test_the_seeded_sizes_carry_their_dimensions(self):
        """An administrator adds a size without code, so the model holds the
        physical stock rather than a Selection."""
        size = self._size("4x6")

        self.assertEqual(size.name, "4x6")
        self.assertEqual(size.width_mm, 101)
        self.assertEqual(size.height_mm, 152)

    def test_a_size_name_is_unique(self):
        """Two records for the same stock would silently break the pairing."""
        with (
            self.assertRaises(IntegrityError),
            mute_logger("odoo.sql_db"),
        ):
            self.env["printing.label.size"].create(
                {"name": "2x4", "width_mm": 50, "height_mm": 101}
            )

    def test_the_label_types_live_here(self):
        """A transport adds its label type without depending on the dashboard.

        The list is owned by this module, so the dashboard consumes it and a
        transport extends it, both through the same dependency.
        """
        report_model = self.env["ir.actions.report"]

        self.assertEqual(report_model._label_report_types(), ["qweb-text"])
        # A type the printer stack can render is not necessarily a label.
        self.assertIn("qweb-pdf", report_model._label_format_map())
        self.assertNotIn("qweb-pdf", report_model._label_report_types())
