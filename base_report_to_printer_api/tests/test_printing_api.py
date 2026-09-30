from unittest.mock import Mock, patch

import requests

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

REQUEST_TARGET = (
    "odoo.addons.base_report_to_printer_api.models.printing_api_server.requests.request"
)


class TestPrintingApi(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env["printing.api.server"].create(
            {
                "name": "Label API",
                "url": "https://labels.example.test/print",
                "method": "post",
                "api_key": "secret",
                "timeout": 12,
            }
        )
        cls.printer = cls.env["printing.printer"].create(
            {
                "name": "API Label Printer",
                "system_name": "LABEL-01",
                "backend": "api",
                "api_server_id": cls.server.id,
            }
        )
        cls.base_printer = cls.env["printing.printer"].create(
            {
                "name": "Local Printer",
                "system_name": "LOCAL",
                "backend": "base",
            }
        )
        cls.printing_action = cls.env["printing.action"].create(
            {"name": "Send to API", "action_type": "server"}
        )
        cls.partner = cls.env["res.partner"].create({"name": "API Partner"})

    def _profile(self, template="partner-label"):
        target_model = self.env["ir.model"].search(
            [("model", "=", "res.partner")], limit=1
        )
        profile = self.env["print.report"].create(
            {
                "name": template,
                "target_model_id": target_model.id,
                "template": template,
            }
        )
        self.env["print.field"].create(
            {
                "report_id": profile.id,
                "source_field": "name",
                "target_field": "label",
            }
        )
        return profile

    def _report(self, report_type="api", with_profile=True):
        report_number = (
            self.env["ir.actions.report"].search_count([("model", "=", "res.partner")])
            + 1
        )
        values = {
            "name": "API integration report",
            "model": "res.partner",
            "report_type": report_type,
            "report_name": f"base_report_to_printer_api.test_report_{report_number}",
            "report_file": f"base_report_to_printer_api.test_report_{report_number}",
            "property_printing_action_id": self.printing_action.id,
            "printing_printer_id": self.printer.id,
        }
        if report_type == "api" and with_profile:
            values["print_report_id"] = self._profile().id
        return self.env["ir.actions.report"].create(values)

    def _success_response(self, message=None):
        response = Mock()
        response.status_code = 200
        response.json.return_value = message if message is not None else {"ok": True}
        response.text = "ok"
        return response

    def test_api_report_type_is_available(self):
        selection = dict(self.env["ir.actions.report"]._fields["report_type"].selection)
        self.assertEqual(selection.get("api"), "API")

    def test_switching_printer_backend_clears_api_endpoint(self):
        printer = self.printer.new({"backend": "base"})
        printer._onchange_backend()
        self.assertFalse(printer.api_server_id)

    def test_api_server_requires_valid_url(self):
        with self.assertRaises(ValidationError):
            self.env["printing.api.server"].create(
                {"name": "Invalid", "url": "not-a-url"}
            )

    def test_api_printer_requires_endpoint(self):
        with self.assertRaises(ValidationError):
            self.env["printing.printer"].create(
                {
                    "name": "Invalid API printer",
                    "system_name": "INVALID",
                    "backend": "api",
                }
            )

    def test_switching_away_from_api_clears_payload_profile(self):
        report = self._report().new({"report_type": "qweb-text"})
        report._onchange_report_type()
        self.assertFalse(report.print_report_id)

    def test_api_report_requires_payload_profile(self):
        with self.assertRaises(ValidationError):
            self._report(with_profile=False)

    def test_qweb_report_cannot_have_payload_profile(self):
        profile = self._profile()
        with self.assertRaises(ValidationError):
            self._report("qweb-text", with_profile=False).write(
                {"print_report_id": profile.id}
            )

    def test_send_uses_configured_http_options(self):
        with patch(
            REQUEST_TARGET,
            return_value=self._success_response(),
        ) as request:
            result = self.server._send({"_template": "partner-label"})

        self.assertTrue(result["success"])
        request.assert_called_once_with(
            "post",
            self.server.url,
            json={"_template": "partner-label"},
            headers={
                "Accept": "application/json",
                "Authorization": "Bearer secret",
            },
            timeout=12,
        )

    def test_send_reports_connection_error(self):
        with patch(
            REQUEST_TARGET,
            side_effect=requests.ConnectionError("offline"),
        ):
            result = self.server._send({"_template": "partner-label"})

        self.assertFalse(result["success"])
        self.assertIn("Could not reach", result["message"])

    def test_standard_print_behavior_exposes_api_backend(self):
        report = self._report()
        result = report.print_action_for_report_name(report.report_name)

        self.assertEqual(result["action"], "server")
        self.assertEqual(result["backend"], "api")
        self.assertEqual(result["printer_id"], self.printer.id)

    def test_api_report_action_skips_external_layout_configuration(self):
        report = self._report()
        with patch.object(
            type(report),
            "_action_configure_external_report_layout",
            side_effect=AssertionError("API reports must not configure a PDF layout"),
        ):
            action = report.report_action(self.partner.ids, data={"label_count": 1})

        self.assertEqual(action["report_type"], "api")
        self.assertEqual(action["id"], report.id)

    def test_api_payload_is_flat_and_does_not_render(self):
        report = self._report()
        with (
            patch.object(
                type(report), "_render_qweb_text", return_value=("^XA", "text")
            ) as render,
            patch(
                REQUEST_TARGET,
                return_value=self._success_response(),
            ) as request,
        ):
            result = report.print_document(
                self.partner.ids,
                data={
                    "label_count": 2,
                    "product_uom_qty": 12,
                    "label": "action data must not win",
                },
            )

        self.assertTrue(result)
        render.assert_not_called()
        payload = request.call_args.kwargs["json"]
        self.assertEqual(
            payload,
            {
                "_template": "partner-label",
                "_printer": "LABEL-01",
                "label_count": 2,
                "product_uom_qty": 12,
                "label": "API Partner",
                "_qty": 1,
            },
        )
        self.assertNotIn("document", payload)
        self.assertNotIn("data", payload)

    def test_api_report_cannot_be_rendered_locally(self):
        report = self._report()
        with self.assertRaisesRegex(UserError, "external API"):
            report._render(report.report_name, self.partner.ids)

    def test_api_report_requires_api_printer(self):
        report = self._report()
        report.printing_printer_id = self.base_printer
        with self.assertRaisesRegex(UserError, "API report"):
            report.print_document(self.partner.ids)

    def test_qweb_report_cannot_use_api_printer(self):
        report = self._report("qweb-text", with_profile=False)
        with self.assertRaisesRegex(UserError, "report of type API"):
            report.print_document(self.partner.ids)

    def test_api_failure_raises_user_error(self):
        report = self._report()
        response = Mock()
        response.status_code = 422
        response.json.return_value = {"error": "invalid label"}
        response.text = "invalid label"
        with (
            patch(REQUEST_TARGET, return_value=response),
            self.assertRaisesRegex(UserError, "invalid label"),
        ):
            report.print_document(self.partner.ids)

    def test_api_sends_one_flat_request_per_record(self):
        second_partner = self.env["res.partner"].create({"name": "Second Partner"})
        report = self._report()
        with patch(
            REQUEST_TARGET,
            return_value=self._success_response(),
        ) as request:
            report.print_document(
                (self.partner + second_partner).ids,
                data={
                    str(self.partner.id): {"label_count": 1},
                    str(second_partner.id): {"label_count": 3},
                },
            )

        self.assertEqual(request.call_count, 2)
        payloads = [call.kwargs["json"] for call in request.call_args_list]
        self.assertEqual(
            payloads,
            [
                {
                    "_template": "partner-label",
                    "_printer": "LABEL-01",
                    "label_count": 1,
                    "label": "API Partner",
                    "_qty": 1,
                },
                {
                    "_template": "partner-label",
                    "_printer": "LABEL-01",
                    "label_count": 3,
                    "label": "Second Partner",
                    "_qty": 1,
                },
            ],
        )

    def test_direct_api_print_document_ignores_rendered_content(self):
        report = self._report()
        with patch(
            REQUEST_TARGET,
            return_value=self._success_response(),
        ) as request:
            self.printer.print_document(
                report,
                b"%PDF-test",
                res_ids=self.partner.ids,
                data={"label_count": 1},
            )

        payload = request.call_args.kwargs["json"]
        self.assertNotIn("document", payload)
        self.assertEqual(payload["_template"], "partner-label")
        self.assertEqual(payload["label_count"], 1)
