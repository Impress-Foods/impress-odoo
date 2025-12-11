import logging
from datetime import datetime, timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    _inherit = "stock.lot"

    def _calculate_expiration_date(self):
        for lot in self:
            if (
                lot.product_id.use_expiration_date
                and len(lot.name) >= 5
                and lot.product_id.default_code[0] == "E"
            ):
                lot_number = lot.name[:5]
                # Assuming 'lot.name' follows the 'YYDDD' format,
                # where 'YY' is the year and 'DDD' is the day of the year.
                year, day = "20" + lot_number[:2], int(lot_number[2:])
                year_date = datetime.fromisoformat(year + "-01-01")
                create_date = year_date + timedelta(days=(day))

                expiration_date = create_date + timedelta(
                    days=lot.product_id.expiration_time
                )
                best_before_date = expiration_date - timedelta(
                    days=lot.product_id.use_time
                )
                removal_date = expiration_date - timedelta(
                    days=lot.product_id.removal_time + 1
                )
                alert_date = expiration_date - timedelta(
                    days=lot.product_id.alert_time + 1
                )

                lot.write(
                    {
                        "expiration_date": expiration_date.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "use_date": best_before_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "removal_date": removal_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "alert_date": alert_date.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

    @api.model
    def _get_lots_to_send_alert(self, alert_date):
        first_pass_date = alert_date - timedelta(days=1)
        lots = self.env["stock.lot"].search([("alert_date", ">=", first_pass_date)])
        lots = lots.filtered(lambda lot: lot.alert_date.date() == alert_date)
        alert_lots = (
            self.env["stock.quant"]
            .search(
                [
                    ("lot_id", "in", lots.ids),
                    ("quantity", ">", 0),
                    ("location_id.usage", "=", "internal"),
                ]
            )
            .mapped("lot_id")
        )
        return alert_lots

    @api.model
    def _cron_send_alert(self):
        today = fields.Date.today()
        lots = self._get_lots_to_send_alert(today)

        if not lots:
            return

        email_template = self.env.ref(
            "impress_expiration_lot.aggregated_lot_expiry_alert"
        )

        email_values = {
            "email_cc": False,
            "auto_delete": False,
            "message_type": "user_notification",
            "recipient_ids": [],
            "partner_ids": [],
            "scheduled_date": False,
            "email_to": email_template.email_to,
        }
        base_url = self.env["ir.config_parameter"].get_param("web.base.url", "")
        body = self.env["ir.ui.view"]._render_template(
            "impress_expiration_lot.body_aggregated_expiry_alert",
            {"today": today, "lots": lots, "base_url": base_url},
        )

        sender_email = self.env["res.company"].browse([1]).email_formatted
        mail = (
            self.env["mail.mail"]
            .sudo()
            .create(
                {
                    "subject": _("Lot alerts for %s" % [today]),
                    "email_from": sender_email,
                    "body_html": body,
                    **email_values,
                }
            )
        )
        mail.send()
