import logging

from odoo import fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class QualityCheck(models.Model):
    _inherit = "quality.check"

    test_report_type = fields.Selection(related="point_id.test_report_type")

    def _get_product_label_action(self, report_type):
        if report_type == "api":
            return self._send_api_label()
        else:
            return super()._get_product_label_action(report_type)

    def _get_lot_label_action(self, report_type):
        if report_type == "api":
            return self._send_api_label()
        else:
            return super()._get_lot_label_action(report_type)

    def _send_api_label(self):
        self.ensure_one()
        report = self.point_id.report_id

        if report.report_type != "api":
            raise ValidationError(
                self.env._(
                    "Trying to print report of type %(type)s via API",
                    type=report.report_type,
                )
            )

        qty = self._get_print_qty()

        record = self._get_record_for_api_report()

        res = report.report_action(
            record.ids,
            data={
                "_qty": qty,
                "_printer": self._get_printer_name(),
                "_job": self._get_print_job_name(),
            },
        )

        res["id"] = report.id
        return res

    def _get_record_for_api_report(self):
        target_model = self.point_id.report_id.print_report_id.target_model_id.model

        match target_model:
            case "stock.lot":
                lot_id = self.workorder_id.finished_lot_ids
                if len(lot_id) > 1:
                    raise ValidationError(
                        self.env._("Cannot send label for multiple lots via API")
                    )

                if not lot_id:
                    raise ValidationError(
                        self.env._("Must specify lot for label printing")
                    )

                return lot_id

            case "product.product":
                product_id = self.product_id
                if len(product_id) > 1:
                    raise ValidationError(
                        self.env._("Cannot send label for multiple products via API")
                    )

                if not product_id:
                    raise ValidationError(
                        self.env._("Must specify product for label printing")
                    )

                return product_id

            case _:
                raise ValidationError(
                    self.env._(
                        "Can only print reports for 'product.product' "
                        "or 'stock.lot' models. Current model: %(model)s",
                        model=target_model,
                    )
                )

    def _get_print_qty(self):
        if self.env.context.get("printing_printing_quantity", False):
            return self.env.context.get("printing_printing_quantity")
        return super()._get_print_qty()

    def _get_printer(self):
        """Resolves printers by priority"""
        self.ensure_one()

        if self.env.context.get("printing_printer_override", False):
            printer = self.env["print.printer"].browse(
                self.env.context.get("printing_printer_override")
            )
            if printer:
                return printer

        if self.point_id.printer_id:
            return self.point_id.printer_id

        if self.workcenter_id.default_printer_id:
            return self.workcenter_id.default_printer_id

        raise ValidationError(
            self.env._("No printer could be found for this print job!")
        )

    def _get_printer_name(self):
        self.ensure_one()
        return self._get_printer().technical_name

    def _get_print_job_name(self):
        self.ensure_one()
        if self.workorder_id:
            return self.workorder_id.display_name
        elif self.production_id:
            return self.production_id.display_name
        else:
            return self.display_name

    def get_print_data(self):
        self.ensure_one()
        report = self.point_id.report_id.print_report_id

        domain = Domain("active", "=", True)

        if report.print_server_id:
            domain += Domain("server_id", "=", report.print_server_id.id)

        printers = self.env["print.printer"].search_read(domain, ["name"])

        record = self._get_record_for_api_report()
        return {
            "printers": printers,
            "_printer_id": self._get_printer().id,
            "_qty": self._get_print_qty(),
            "data": self.point_id.report_id.print_report_id._render_json_payload(
                record
            ),
        }
