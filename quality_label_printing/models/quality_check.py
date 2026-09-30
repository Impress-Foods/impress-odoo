from odoo import models
from odoo.exceptions import UserError


class QualityCheck(models.Model):
    _inherit = "quality.check"

    def _get_label_target(self):
        """Resolve the record this check's label is about.

        The work order already knows: the finished lot for a tracked product,
        otherwise the product itself.  Several finished lots would mean several
        labels, so the first one stands, and the operator can still print
        another lot's label from the picking dashboard if that is what they
        meant.
        """
        self.ensure_one()
        if self.product_id.tracking == "none":
            return self.product_id
        lots = self.workorder_id.finished_lot_ids
        if not lots:
            raise UserError(
                self.env._("You did not set a lot/serial number for the final product.")
            )
        return lots[:1]

    def _get_label_report(self):
        """Return the report this step prints, defaulting like the dashboard."""
        self.ensure_one()
        report = self.point_id.label_report_id
        if not report:
            report = self.env["ir.actions.report"]._get_default_dashboard_report(
                self._get_label_target()._name
            )
        if not report:
            raise UserError(
                self.env._("No label report is configured for this quality step.")
            )
        return report

    def action_print(self):
        """Open the printer picker for this step's label.

        Everything a label needs is already decided by the step and the work
        order, so the picker only offers the two things an operator may
        reasonably change: how many labels, and which machine.

        ``next_check_id`` is left out on purpose.  The check only advances once
        the label is away, which the picker does after printing, so a printer
        that is out of paper holds the operator here instead of quietly
        passing a step.
        """
        self.ensure_one()
        # Resolving first means a step that cannot print says so now, rather
        # than after the operator has filled the picker in.
        self._get_label_target()
        self._get_label_report()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "quality_label_printing.quality_check_printer_picker_action"
        )
        # The picker is a dialog, so it is created from this action's context
        # rather than being pointed at a record. The check travels that way.
        action["context"] = {"default_quality_check_id": self.id}
        return action
