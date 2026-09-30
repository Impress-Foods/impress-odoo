from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestQualityLabelPrinting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.printer = cls._make_printer("QLP Printer", "zpl")
        cls.report = cls._make_report("QLP Lot Label", model="stock.lot")
        cls.env["ir.ui.view"].create(
            {
                "name": "QLP Test Label",
                "type": "qweb",
                "arch": (
                    '<t t-name="quality_label_printing.test_label">'
                    '<t t-foreach="docs" t-as="doc">'
                    '<span t-out="doc.display_name"/>'
                    "</t>"
                    "</t>"
                ),
            }
        )
        cls.env["ir.model.data"].create(
            {
                "name": "test_label",
                "module": "quality_label_printing",
                "model": "ir.ui.view",
                "res_id": cls.env["ir.ui.view"]
                .search([("name", "=", "QLP Test Label")], limit=1)
                .id,
                "noupdate": True,
            }
        )

    @classmethod
    def _make_printer(cls, name, label_format=False):
        return cls.env["printing.printer"].create(
            {
                "name": name,
                "system_name": name.lower().replace(" ", "-"),
                "backend": "base",
                "label_format": label_format,
            }
        )

    @classmethod
    def _make_report(cls, name, model):
        return cls.env["ir.actions.report"].create(
            {
                "name": name,
                "model": model,
                "report_type": "qweb-text",
                "report_name": "quality_label_printing.test_label",
                "is_dashboard_report": True,
            }
        )

    def _make_check(self, point_vals, tracking="lot", qty=2.0):
        product = self.env["product.product"].create(
            {
                "name": "QLP Product",
                "type": "consu",
                "is_storable": True,
                "tracking": tracking,
            }
        )
        workcenter = self.env["mrp.workcenter"].create({"name": "QLP Workcenter"})
        bom = self.env["mrp.bom"].create(
            {
                "product_id": product.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
                "operation_ids": [
                    Command.create({"name": "QLP Step", "workcenter_id": workcenter.id})
                ],
            }
        )
        point = self.env["quality.point"].create(
            {
                "name": "QLP Print Label",
                "product_ids": [Command.link(product.id)],
                "operation_id": bom.operation_ids.id,
                "test_type_id": self.env.ref("mrp_workorder.test_type_print_label").id,
                **point_vals,
            }
        )
        production = self.env["mrp.production"].create(
            {"bom_id": bom.id, "product_qty": qty}
        )
        production.action_confirm()
        check = production.workorder_ids.current_quality_check_id
        self.assertEqual(check.point_id, point)
        return check, product

    def _with_lot(self, check, name="QLP-LOT"):
        lot = self.env["stock.lot"].create(
            {"name": name, "product_id": check.product_id.id}
        )
        check.production_id.lot_producing_ids = lot
        return lot

    def _open_picker(self, check):
        """Open the picker the way the shop floor does, through ``action_print``."""
        action = check.action_print()
        return (
            self.env["quality.check.printer.picker"]
            .with_context(**action["context"])
            .create({})
        )

    def test_the_target_is_the_lot_when_tracked_and_the_product_otherwise(self):
        check, _product = self._make_check({"label_report_id": self.report.id})
        lot = self._with_lot(check)
        self.assertEqual(check._get_label_target(), lot)

        report = self._make_report("QLP Product Label", model="product.product")
        untracked, product = self._make_check(
            {"label_report_id": report.id}, tracking="none"
        )
        self.assertEqual(untracked._get_label_target(), product)

    def test_a_tracked_product_without_a_lot_refuses(self):
        check, _product = self._make_check({"label_report_id": self.report.id})

        with self.assertRaises(UserError):
            check._get_label_target()

    def test_action_print_opens_the_picker_with_a_usable_handoff(self):
        """The client maps over action.views unconditionally, and the dialog is
        created from the action's context, so both have to be right or the shop
        floor breaks before the dialog opens."""
        check, _product = self._make_check({"label_report_id": self.report.id})
        self._with_lot(check)

        action = check.action_print()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "quality.check.printer.picker")
        self.assertTrue(action["views"])
        self.assertEqual(action["context"]["default_quality_check_id"], check.id)
        # The check may only advance once the label is away.
        self.assertNotIn("next_check_id", action)

    def test_the_picker_starts_on_the_step_printer_and_quantity(self):
        check, _product = self._make_check(
            {"label_report_id": self.report.id, "label_printer_id": self.printer.id}
        )
        self._with_lot(check)
        check.workorder_id.qty_producing = 4.0

        picker = self._open_picker(check)

        self.assertEqual(picker.report_id, self.report)
        self.assertEqual(picker.printer_id, self.printer)
        self.assertEqual(picker.copies, 4)

    def test_the_picker_falls_back_on_the_report_printer(self):
        self.report.write({"printing_printer_id": self.printer.id})
        check, _product = self._make_check({"label_report_id": self.report.id})
        self._with_lot(check)

        self.assertEqual(self._open_picker(check).printer_id, self.printer)

    def test_a_printer_that_cannot_be_used_is_not_offered(self):
        """A step naming a wrong or archived machine is left for the operator to
        correct, rather than defaulted to at print time."""
        check, _product = self._make_check(
            {"label_report_id": self.report.id, "label_printer_id": self.printer.id}
        )
        self._with_lot(check)
        self.printer.sudo().write({"active": False})
        action = check.action_print()

        values = (
            self.env["quality.check.printer.picker"]
            .with_context(**action["context"])
            .default_get(["printer_id"])
        )

        self.assertFalse(values["printer_id"])

    def test_confirm_prints_then_advances(self):
        check, _product = self._make_check(
            {"label_report_id": self.report.id, "label_printer_id": self.printer.id}
        )
        lot = self._with_lot(check)
        picker = self._open_picker(check)
        picker.copies = 3

        with patch.object(type(self.printer), "print_file", autospec=True) as spy:
            action = picker.action_confirm()

        self.assertEqual(action["type"], "ir.actions.act_window_close")
        self.assertEqual([call.args[0] for call in spy.call_args_list], [self.printer])
        # The label count and the quantity a label stands for are separate.
        self.assertEqual(
            self.report._print_label_data(lot, 3)[str(lot.id)]["label_count"], 3
        )
        self.assertEqual(check.quality_state, "pass")

    def test_a_failed_print_leaves_the_step_open(self):
        """The step may only advance once the label is away, so a printer that
        refuses the job leaves the operator on a check they can reprint."""
        check, _product = self._make_check(
            {"label_report_id": self.report.id, "label_printer_id": self.printer.id}
        )
        self._with_lot(check)
        picker = self._open_picker(check)

        with (
            patch.object(
                type(self.printer), "print_file", side_effect=OSError("cups is down")
            ),
            self.assertRaises(UserError),
        ):
            picker.action_confirm()

        self.assertEqual(check.quality_state, "none")

    def test_the_step_printer_wins_over_a_per_user_override(self):
        """``behaviour()`` applies a per-user report action last, so anything
        resolving a printer that way would override the step's choice."""
        self.env["printing.report.xml.action"].create(
            {
                "report_id": self.report.id,
                "user_id": self.env.user.id,
                "action": "server",
                "printer_id": self._make_printer("QLP Override", "zpl").id,
            }
        )
        check, _product = self._make_check(
            {"label_report_id": self.report.id, "label_printer_id": self.printer.id}
        )
        self._with_lot(check)
        picker = self._open_picker(check)

        with patch.object(type(self.printer), "print_file", autospec=True) as spy:
            picker.action_confirm()

        self.assertEqual([call.args[0] for call in spy.call_args_list], [self.printer])

    def test_confirm_refuses_an_unusable_pick(self):
        """A bypassed selection still has to be refused server-side, and the
        step must stay open."""
        pdf_printer = self._make_printer("QLP PDF Printer", "pdf")
        cases = [
            ("wrong format", pdf_printer, 1, UserError),
            ("zero labels", self.printer, 0, ValidationError),
        ]
        for label, printer, copies, error in cases:
            with self.subTest(label):
                check, _product = self._make_check(
                    {
                        "label_report_id": self.report.id,
                        "label_printer_id": self.printer.id,
                    }
                )
                self._with_lot(check)
                picker = self._open_picker(check)
                picker.printer_id = printer
                picker.copies = copies

                with self.assertRaises(error):
                    picker.action_confirm()

                self.assertEqual(check.quality_state, "none")

    def test_a_step_refuses_a_printer_that_cannot_print_its_report(self):
        pdf_printer = self._make_printer("QLP Step PDF", "pdf")

        with self.assertRaises(ValidationError):
            self._make_check(
                {
                    "label_report_id": self.report.id,
                    "label_printer_id": pdf_printer.id,
                }
            )
