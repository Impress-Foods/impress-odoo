import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .schema import Rate, RateStatus

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    clickship_tracking_url = fields.Char(copy=False)
    clickship_shipment_id = fields.Char(copy=False)
    clickship_service_id = fields.Char(copy=False)
    clickship_rate_needed = fields.Boolean(compute="_compute_clickship_rate_needed")

    @api.depends(
        "clickship_service_id",
    )
    def _compute_clickship_rate_needed(self):
        for picking in self:
            if (
                picking.carrier_id.delivery_type == "clickship"
                and not picking.clickship_service_id
            ):
                picking.clickship_rate_needed = True
            else:
                picking.clickship_rate_needed = False

    def action_get_clickship_rates(self) -> dict:
        response: RateStatus = self.carrier_id.clickship_get_raw_rates(self)
        raw_rates = response.rates
        rates = self._clickship_parse_rates(raw_rates)

        _logger.warning(rates)

        action = {
            "res_model": "wizard.clickship_rates",
            "type": "ir.actions.act_window",
            "target": "new",
            "view_type": "form",
            "view_mode": "form",
            "views": [(False, "form")],
            "context": {
                "default_picking_id": self.id,
                "default_rate_ids": [rate.id for rate in rates],
            },
        }
        return action

    def _clickship_parse_rates(self, rates: list[Rate]):
        rate_data = []
        for rate in rates:
            currency = self.env["res.currency"].search(
                [("name", "=", rate.total.currency)], limit=1
            )

            if not currency:
                raise ValidationError(
                    _(f"Could not find currency with name {rate.total.currency}")
                )

            if rate.transit_time_not_available:
                continue

            data = {
                "service_id": rate.service_id,
                "service_name": rate.service_name,
                "carrier_name": rate.carrier_name,
                "total": float(rate.total.value) / 100,
                "currency_id": currency.id,
                "transit_time": rate.transit_time_days,
                "transit_time_valid": not rate.transit_time_not_available,
            }
            rate_data.append(data)

        return self.env["clickship.rate"].create(rate_data)

    def _get_fields_stock_barcode(self):
        res = super()._get_fields_stock_barcode()
        res.append("clickship_rate_needed")
        return res
