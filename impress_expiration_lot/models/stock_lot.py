from datetime import datetime, timedelta

from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    origin_date = fields.Datetime()

    @api.model
    def _parse_lot_number(self, name: str) -> datetime | None:
        if not name or len(name) < 5 or not name[:5].isnumeric():
            return None

        try:
            return datetime.strptime(name[:5], "%y%j").replace(hour=12, minute=0)
        except ValueError:
            return None

    @api.model
    def _get_date_vals(self, name: str, product=None) -> dict:
        if not product or not product.use_expiration_date:
            return {}

        production = self._parse_lot_number(name)
        if not production:
            return {}

        to_string = fields.Datetime.to_string
        tmpl = product.product_tmpl_id
        exp = production + timedelta(days=tmpl.expiration_time or 0)

        return {
            "origin_date": to_string(production),
            "expiration_date": to_string(exp),
            "use_date": to_string(exp - timedelta(days=tmpl.use_time or 0)),
            "removal_date": to_string(exp - timedelta(days=tmpl.removal_time or 0)),
            "alert_date": to_string(exp - timedelta(days=tmpl.alert_time or 0)),
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.update({"origin_date": fields.Datetime.now()})
            if "name" in vals and "product_id" in vals:
                product = self.env["product.product"].browse(vals["product_id"])
                date_vals = self._get_date_vals(vals["name"], product)
                vals.update(date_vals)

        return super().create(vals_list)

    def write(self, vals):
        if "name" in vals and "expiration_date" not in vals:
            res = True
            for lot in self:
                product = self.env["product.product"].browse(
                    vals.get("product_id", lot.product_id.id)
                )
                date_vals = lot._get_date_vals(vals["name"], product)
                res = super(StockLot, lot).write({**vals, **date_vals}) and res
            return res

        return super().write(vals)

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
                    "subject": self.env._("Lot alerts for %s", today),
                    "email_from": sender_email,
                    "body_html": body,
                    **email_values,
                }
            )
        )
        mail.send()
