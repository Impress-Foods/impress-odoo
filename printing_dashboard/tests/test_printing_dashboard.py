from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools.view_validation import get_expression_field_names


class TestPrintingDashboard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.ui.view"].create(
            {
                "name": "Dashboard Test Label",
                "key": "dashboard_test_label",
                "type": "qweb",
                "arch_base": '<t t-name="dashboard_test_label">LABEL</t>',
            }
        )
        # A report that takes its records from the context rather than docids,
        # the way label_printing_wizard's reports do.
        cls.env["ir.ui.view"].create(
            {
                "name": "Dashboard Test Context Label",
                "key": "dashboard_test_context_label",
                "type": "qweb",
                "arch_base": '<t t-name="dashboard_test_context_label">'
                '<t t-set="ambient" t-value="env.context.get(\'active_ids\') or []"/>'
                "<t t-raw=\"'|'.join(env['product.product'].browse(ambient)"
                ".mapped('display_name'))\"/>"
                "</t>",
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Dashboard Product", "type": "consu"}
        )
        cls.report = cls._make_report("Dashboard Product Report")
        cls.label_report = cls._make_report("Dashboard Product Label")
        # backend="base" keeps print_file a no-op, so nothing reaches a printer.
        cls.pdf_printer = cls._make_printer("Dashboard PDF Printer", "pdf")
        cls.zpl_printer = cls._make_printer("Dashboard ZPL Printer", "zpl")
        cls.spare_zpl_printer = cls._make_printer("Dashboard Spare ZPL", "zpl")
        cls.wide_zpl_printer = cls._make_printer("Dashboard ZPL 4x6", "zpl", "4x6")

    @classmethod
    def _make_report(cls, name, size="2x4", template="dashboard_test_label"):
        return cls.env["ir.actions.report"].create(
            {
                "name": name,
                "model": "product.product",
                "report_type": "qweb-text",
                "label_size_id": cls._size(size).id,
                "report_name": template,
                "is_dashboard_report": True,
            }
        )

    @classmethod
    def _size(cls, name):
        return cls.env.ref(f"printing_label_format.size_{name}")

    @classmethod
    def _make_printer(cls, name, label_format=False, label_size="2x4"):
        return cls.env["printing.printer"].create(
            {
                "name": name,
                "system_name": name.lower().replace(" ", "-"),
                "backend": "base",
                "label_format": label_format,
                "label_size_id": cls._size(label_size).id if label_size else False,
            }
        )

    def _dashboard_from_action(self, action):
        """Build the transient the way the client does, from default_* keys."""
        defaults = {
            key[len("default_") :]: value
            for key, value in action["context"].items()
            if key.startswith("default_")
        }
        return self.env["printing.dashboard"].new(defaults)

    def _dashboard(self, report, printer=None, product=None):
        product = product or self.product
        return self.env["printing.dashboard"].create(
            {
                "product_id": product.id,
                "report_id": report.id,
                "printer_id": printer.id if printer else False,
            }
        )

    def _make_picking(self, product, qty=1.0, lot=None, extra_move=False):
        move_line = Command.create(
            {
                "product_id": product.id,
                "product_uom_id": product.uom_id.id,
                "quantity": qty,
                "lot_id": lot.id if lot else False,
            }
        )
        moves = [
            Command.create(
                {
                    "product_id": product.id,
                    "product_uom_qty": qty,
                    "product_uom": product.uom_id.id,
                    "move_line_ids": [move_line],
                }
            )
        ]
        if extra_move:
            other = self.env["product.product"].create(
                {"name": "Dashboard Second Product", "type": "consu"}
            )
            moves.append(
                Command.create(
                    {
                        "product_id": other.id,
                        "product_uom_qty": 1.0,
                        "product_uom": other.uom_id.id,
                    }
                )
            )
        return self.env["stock.picking"].create(
            {
                "picking_type_id": self.env.ref("stock.picking_type_in").id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.env.ref("stock.stock_location_stock").id,
                "move_ids": moves,
            }
        )

    def _print_and_capture(self, dashboard):
        """Print through the dashboard, returning every printer handed the label."""
        with patch.object(type(self.zpl_printer), "print_file", autospec=True) as spy:
            dashboard.action_print()
        return [call.args[0] for call in spy.call_args_list]

    def _printed_document(self, dashboard):
        """Return the document action_print actually sent to the printer.

        print_document writes the content to a temporary file and removes it
        once print_file returns, so it has to be read from inside the call.
        """
        documents = []

        def _read(printer, file_name, report=None, **print_opts):
            with open(file_name, "rb") as handle:
                documents.append(handle.read())

        with patch.object(
            type(dashboard.printer_id), "print_file", autospec=True, side_effect=_read
        ):
            dashboard.action_print()
        return documents

    # -- opening -----------------------------------------------------------

    def test_a_source_opens_a_prefilled_dashboard(self):
        """The defaults travel on the action, and the client creates the record."""
        action = self.product.action_open_print_dashboard()

        self.assertEqual(action["res_model"], "printing.dashboard")
        self.assertFalse(action["res_id"])
        dashboard = self._dashboard_from_action(action)
        self.assertEqual(dashboard.source_model, "product.product")
        self.assertEqual(dashboard.product_id, self.product)
        # A default report is picked for the model, of the label type.
        self.assertEqual(dashboard.report_id.report_type, "qweb-text")
        self.assertTrue(dashboard.report_id.is_dashboard_report)

    def test_action_open_for_record_declines_a_non_source(self):
        partner = self.env["res.partner"].create({"name": "Dashboard Navbar Partner"})

        self.assertFalse(
            self.env["printing.dashboard"].action_open_for_record(
                "res.partner", partner.id
            )
        )
        self.assertFalse(
            self.env["printing.dashboard"].action_open_for_record(
                "product.product", False
            )
        )

    # -- target resolution -------------------------------------------------

    def test_a_transfer_narrows_to_its_lot_or_opens_empty(self):
        """A single move narrows to its lot; several leave the target open so
        the operator chooses, rather than defaulting to the picking."""
        lot = self.env["stock.lot"].create(
            {"name": "DASHBOARD-PICK-001", "product_id": self.product.id}
        )
        single = self._make_picking(self.product, lot=lot)
        many = self._make_picking(self.product, lot=lot, extra_move=True)

        single_dashboard = self._dashboard_from_action(
            single.action_open_print_dashboard()
        )
        many_dashboard = self._dashboard_from_action(many.action_open_print_dashboard())

        self.assertEqual(single_dashboard.target, lot)
        self.assertFalse(many_dashboard.target)
        self.assertEqual(many_dashboard.source_model, "stock.picking")

    def test_a_transfer_reads_the_quantity_it_received(self):
        """Labels taken off a transfer state what was received, not zero."""
        lot = self.env["stock.lot"].create(
            {"name": "DASHBOARD-QTY-LOT", "product_id": self.product.id}
        )
        picking = self._make_picking(self.product, qty=7.0, lot=lot)

        dashboard = self._dashboard_from_action(picking.action_open_print_dashboard())

        self.assertEqual(dashboard.target, lot)
        self.assertEqual(dashboard.product_uom_qty, 7.0)

    def test_a_recordset_target_resolves_to_its_model_and_id(self):
        lot = self.env["stock.lot"].create(
            {"name": "DASHBOARD-RESOLVE-001", "product_id": self.product.id}
        )
        source = self.env["printing.dashboard.source"]

        self.assertEqual(
            source._resolve_target({"target": self.product}),
            ("product.product", self.product.id, False),
        )
        self.assertEqual(
            source._resolve_target({"target": lot}),
            ("stock.lot", self.product.id, lot.id),
        )
        self.assertEqual(source._resolve_target({}), ("product.product", False, False))

    # -- guards ------------------------------------------------------------

    def test_a_transfer_refuses_a_target_it_does_not_own(self):
        """The pickers are narrowed, but a domain is client-side, so the source
        still rejects a target that was set another way -- a prefilled context,
        a stale source, a programmatic write."""
        lot = self.env["stock.lot"].create(
            {"name": "DASHBOARD-GUARD-001", "product_id": self.product.id}
        )
        unrelated = self.env["product.product"].create(
            {"name": "Dashboard Unrelated Product", "type": "consu"}
        )
        picking = self._make_picking(self.product, lot=lot)
        source = self._dashboard_from_action(
            picking.action_open_print_dashboard()
        )._get_source_record()

        source._check_target_allowed("stock.lot", lot)
        with self.assertRaises(UserError):
            source._check_target_allowed("product.product", unrelated)

    def test_a_transfer_narrows_its_pickers_to_its_own_records(self):
        """Poka-yoke: a target the transfer does not own is never offered, so it
        cannot be chosen in the first place."""
        lot = self.env["stock.lot"].create(
            {"name": "DASHBOARD-NARROW-001", "product_id": self.product.id}
        )
        unrelated = self.env["product.product"].create(
            {"name": "Dashboard Narrowed Out", "type": "consu"}
        )
        picking = self._make_picking(self.product, lot=lot)
        dashboard = self._dashboard_from_action(picking.action_open_print_dashboard())

        self.assertTrue(dashboard.restrict_targets)
        # _origin unwraps the NewId that new() puts around an x2many.
        self.assertEqual(dashboard.available_target_product_ids._origin, self.product)
        self.assertEqual(dashboard.available_target_lot_ids._origin, lot)
        self.assertNotIn(unrelated, dashboard.available_target_product_ids._origin)

    def test_a_source_without_candidates_keeps_its_pickers_open(self):
        """An empty mapping means "no restriction", not "nothing is allowed", so
        the domain has to branch on it -- otherwise every product vanishes from
        the picker for the sources that impose no restriction."""
        dashboard = self._dashboard_from_action(
            self.product.action_open_print_dashboard()
        )

        self.assertFalse(dashboard.restrict_targets)
        self.assertFalse(dashboard.available_target_product_ids)
        self.assertFalse(dashboard.available_target_lot_ids)
        self.assertIn(
            "if restrict_targets",
            self.env["printing.dashboard"]._fields["product_id"].domain,
        )

    def test_every_field_a_picker_domain_names_is_loaded_by_the_form(self):
        """A domain is evaluated against the loaded record, so a field it names
        that the form never loads is silently absent and the clause collapses.

        The view is where that goes wrong: a domain on a field node replaces the
        field's own domain, so the field is never even fetched.  That is how the
        lot picker stopped being narrowed while the server tests stayed green.
        The picker domains therefore live on the fields and nowhere else.
        """
        dashboard = self.env["printing.dashboard"]
        loaded = dashboard.get_view(view_type="form")["models"]["printing.dashboard"]

        for field in dashboard._fields.values():
            if not (field.relational and isinstance(field.domain, str)):
                continue
            named = {
                name
                for name in get_expression_field_names(field.domain)
                if name in dashboard._fields
            }
            self.assertTrue(named, f"{field.name} no longer narrows on its own fields")
            for name in named:
                self.assertIn(name, loaded, f"{field.name} names unloaded {name}")

    def test_a_document_cannot_be_flagged_as_a_dashboard_report(self):
        """A packing slip ticked into the flag would be offered as a label."""
        with self.assertRaises(ValidationError):
            self.env["ir.actions.report"].create(
                {
                    "name": "Dashboard Packing Slip",
                    "model": "product.product",
                    "report_type": "qweb-pdf",
                    "report_name": "base.report_partner",
                    "is_dashboard_report": True,
                }
            )

    def test_no_default_report_when_the_model_only_has_documents(self):
        self.env["ir.actions.report"].create(
            {
                "name": "Dashboard Partner Document",
                "model": "res.partner",
                "report_type": "qweb-pdf",
                "report_name": "base.report_partner",
            }
        )

        self.assertFalse(
            self.env["ir.actions.report"]._get_default_dashboard_report("res.partner")
        )

    def test_printing_refuses_what_the_command_guards(self):
        """Copies, printer compatibility and the report/target model all fail
        before anything reaches a printer."""
        cases = [
            ("zero copies", {"copies": 0}, self.zpl_printer, ValidationError),
            ("no printer", {}, None, UserError),
            ("wrong format", {}, self.pdf_printer, UserError),
            ("wrong size", {}, self.wide_zpl_printer, UserError),
        ]
        for label, overrides, printer, error in cases:
            with self.subTest(label):
                dashboard = self.env["printing.dashboard"].create(
                    {
                        "product_id": self.product.id,
                        "report_id": self.label_report.id,
                        "printer_id": printer.id if printer else False,
                        **overrides,
                    }
                )
                with self.assertRaises(error):
                    dashboard.action_print()

    def test_a_report_from_another_model_is_refused(self):
        dashboard = self.env["printing.dashboard"].create(
            {"product_id": self.product.id, "report_id": self.label_report.id}
        )
        dashboard.target_model = "stock.lot"

        with self.assertRaises(UserError):
            dashboard.action_print()

    # -- printing ----------------------------------------------------------

    def test_the_chosen_printer_receives_the_label(self):
        """The printer that was picked is the one that prints.

        The client dispatchers resolve a printer from the report with a context
        they build themselves, so a printer carried in an action never survives.
        """
        dashboard = self._dashboard(self.label_report, self.zpl_printer)

        self.assertEqual(self._print_and_capture(dashboard), [self.zpl_printer])

    def test_a_per_user_override_does_not_beat_the_chosen_printer(self):
        """``behaviour()`` applies a per-user report action last, so anything
        resolving a printer that way would override the operator's pick."""
        self.env["printing.report.xml.action"].create(
            {
                "report_id": self.label_report.id,
                "user_id": self.env.user.id,
                "action": "server",
                "printer_id": self.spare_zpl_printer.id,
            }
        )
        dashboard = self._dashboard(self.label_report, self.zpl_printer)

        self.assertEqual(self._print_and_capture(dashboard), [self.zpl_printer])

    def test_one_batch_prints_once(self):
        """The render must not also print on the report's own default."""
        self.label_report.write({"printing_printer_id": self.spare_zpl_printer.id})
        dashboard = self._dashboard(self.label_report, self.zpl_printer)

        self.assertEqual(len(self._print_and_capture(dashboard)), 1)

    def test_a_report_reading_the_context_still_prints_the_target(self):
        """A report may take its records from the context rather than docids.

        The dashboard is a target="new" dialog, so that context is the dialog's
        own rather than the selection, and a report preferring it renders
        whichever product the context carried -- a real record printed with
        another record's payload, which looks like a valid label for the wrong
        product rather than an error.
        """
        unrelated = self.env["product.product"].create(
            {"name": "Dashboard Ambient Product", "type": "consu"}
        )
        # Built here rather than in setUpClass: an extra dashboard report in the
        # shared fixture changes which report _get_default_dashboard_report
        # picks for every other test.
        context_report = self._make_report(
            "Dashboard Context Report", template="dashboard_test_context_label"
        )
        dashboard = self._dashboard(context_report, self.zpl_printer)

        documents = self._printed_document(
            dashboard.with_context(active_ids=unrelated.ids)
        )

        self.assertEqual(len(documents), 1)
        self.assertIn(self.product.display_name, documents[0].decode())
        self.assertNotIn(unrelated.display_name, documents[0].decode())

    def test_the_report_printer_is_the_default(self):
        """base_report_to_printer already knows where this report prints."""
        self.label_report.write({"printing_printer_id": self.zpl_printer.id})
        action = self.env["printing.dashboard"].open_from_source(self.product)

        self.assertEqual(
            self._dashboard_from_action(action).printer_id, self.zpl_printer
        )

    def test_an_incompatible_or_archived_printer_is_not_offered(self):
        """A misconfiguration to fix, not something to paper over."""
        self.label_report.write({"printing_printer_id": self.pdf_printer.id})
        incompatible = self._dashboard_from_action(
            self.env["printing.dashboard"].open_from_source(self.product)
        )
        self.assertFalse(incompatible.printer_id.id)

        self.label_report.write({"printing_printer_id": self.zpl_printer.id})
        self.zpl_printer.sudo().write({"active": False})
        archived = self._dashboard_from_action(
            self.env["printing.dashboard"].open_from_source(self.product)
        )
        self.assertFalse(archived.printer_id.id)

    def test_a_printer_failure_reaches_the_operator(self):
        """The client dispatchers swallow print errors, leaving nothing to act
        on; printing server-side surfaces them."""
        dashboard = self._dashboard(self.label_report, self.zpl_printer)

        with (
            patch.object(
                type(self.zpl_printer),
                "print_file",
                side_effect=OSError("cups is down"),
            ),
            self.assertRaises(UserError),
        ):
            dashboard.action_print()

    def test_a_transport_report_type_has_no_qweb_renderer(self):
        """A type a transport owns renders its own document, so it must not be
        sent to a QWeb renderer it does not have."""
        report = self.env["ir.actions.report"].create(
            {
                "name": "Dashboard HTML Report",
                "model": "product.product",
                "report_type": "qweb-html",
                "report_name": "dashboard_test_label",
            }
        )

        self.assertIsNone(report._label_renderer_name())

    def test_the_payload_is_keyed_by_target_and_counts_labels(self):
        self.assertEqual(
            self.label_report._print_label_data(self.product, copies=3),
            {str(self.product.id): {"label_count": 3}},
        )
        # A zero quantity is omitted rather than encoded as zero.
        self.assertEqual(
            self.label_report._print_label_data(self.product, copies=2),
            {str(self.product.id): {"label_count": 2}},
        )

    # -- onchange: the printer and the label follow each other -------------

    def test_changing_report_drops_a_printer_that_no_longer_fits(self):
        undeclared = self._make_printer("Dashboard Undeclared", False)
        dashboard = self.env["printing.dashboard"].new(
            {"report_id": self.report.id, "printer_id": undeclared.id}
        )

        dashboard.report_id = self.label_report
        dashboard._onchange_report_id()

        self.assertFalse(dashboard.printer_id.id)

    def test_changing_target_model_resets_the_report(self):
        lot = self.env["stock.lot"].create(
            {"name": "DASHBOARD-SWITCH-001", "product_id": self.product.id}
        )
        dashboard = self.env["printing.dashboard"].new(
            {
                "product_id": self.product.id,
                "lot_id": lot.id,
                "report_id": self.label_report.id,
            }
        )

        dashboard.target_model = "product.product"
        dashboard._onchange_target_model()

        self.assertFalse(dashboard.lot_id)
        self.assertTrue(dashboard.report_id)

    def test_changing_product_redefaults_packaging(self):
        kg_uom = self.env.ref("uom.product_uom_kgm")
        other = self.env["product.product"].create(
            {"name": "Dashboard Kg Product", "type": "consu", "uom_id": kg_uom.id}
        )
        dashboard = self.env["printing.dashboard"].new(
            {"product_id": self.product.id, "product_uom_id": self.product.uom_id.id}
        )

        dashboard.product_id = other
        dashboard._onchange_product_id()

        self.assertEqual(dashboard.product_uom_id, other.uom_id)

    def test_a_printer_with_no_label_is_flagged(self):
        odd = self._make_printer("Dashboard 3x3", "zpl", "3x3")
        dashboard = self.env["printing.dashboard"].new(
            {"product_id": self.product.id, "printer_id": odd.id}
        )

        self.assertFalse(dashboard.printer_has_report)

    def test_a_template_is_never_resolved_as_a_product(self):
        template = self.env["product.template"].create(
            {"name": "Dashboard Template", "type": "consu"}
        )
        target_model, product_id, _lot_id = self.env[
            "printing.dashboard.source"
        ]._resolve_target({"target": template})

        self.assertEqual(target_model, "product.product")
        self.assertFalse(product_id)
