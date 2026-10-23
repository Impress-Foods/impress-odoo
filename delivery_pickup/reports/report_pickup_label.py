import base64

from odoo import models, tools


class ReportPickupLabel(models.AbstractModel):
    _name = "report.delivery_pickup.pickup_delivery_label"
    _description = "Model for pickup_delivery_label report"

    def _get_report_values(self, docids: list[int], data: dict | None = None) -> dict:
        pickings = self.env["stock.picking"].browse(docids)
        packages = {}
        labels = []

        for picking in pickings:
            picking_packages = self.env["stock.package.history"].search(
                [("picking_ids", "=", picking.id)]
            )
            packages[picking.id] = picking_packages
            labels.extend(
                {
                    "picking": picking,
                    "package": package,
                    "number": index,
                    "total": len(picking_packages),
                }
                for index, package in enumerate(picking_packages, start=1)
            )

        return {"docs": pickings, "packages": packages, "labels": labels}


class ReportPickupLabelPdf(models.AbstractModel):
    _name = "report.delivery_pickup.pickup_delivery_label_pdf"
    _description = "Model for pickup_delivery_label_pdf report"

    def _get_report_values(self, docids: list[int], data: dict | None = None) -> dict:
        values = self.env[
            "report.delivery_pickup.pickup_delivery_label"
        ]._get_report_values(docids, data)
        values["logo_data_uri"] = self._get_logo_data_uri()
        return values

    @staticmethod
    def _get_logo_data_uri() -> str:
        with tools.file_open(
            "delivery_pickup/static/src/img/impress_logo.png", "rb"
        ) as logo:
            return "data:image/png;base64," + base64.b64encode(logo.read()).decode()
