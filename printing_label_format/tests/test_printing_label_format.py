from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestPrintingLabelFormat(TransactionCase):
    def _make_report(self, name, report_type, size="2x4"):
        return self.env["ir.actions.report"].create(
            {
                "name": name,
                "model": "product.product",
                "report_type": report_type,
                "label_size": size,
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
                "label_size": size,
            }
        )

    def test_label_format_of_report(self):
        printer_obj = self.env["printing.printer"]
        pdf_report = self._make_report("PLF PDF Label", "qweb-pdf")
        zpl_report = self._make_report("PLF ZPL Label", "qweb-text")

        self.assertEqual(printer_obj._label_format_of(pdf_report), "pdf")
        self.assertEqual(printer_obj._label_format_of(zpl_report), "zpl")

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

        self.assertIsNone(self.env["printing.printer"]._label_format_of(html_report))
        self.assertFalse(zpl_printer._supports_report(html_report))

    def test_the_map_is_where_routing_lives(self):
        # Extending the map is all it takes to route a report type to a format
        # that is already declared, so a module adding a format only has to
        # list it in the selection and map it here.
        printer_obj = self.env["printing.printer"]
        html_report = self._make_report("PLF HTML Label", "qweb-html")
        zpl_printer = self._make_printer("PLF ZPL", "zpl")
        pdf_printer = self._make_printer("PLF PDF", "pdf")

        with patch.object(
            type(printer_obj),
            "_label_format_map",
            return_value={"qweb-pdf": "pdf", "qweb-text": "zpl", "qweb-html": "pdf"},
        ):
            self.assertEqual(printer_obj._label_format_of(html_report), "pdf")
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
