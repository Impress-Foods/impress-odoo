from datetime import date, datetime, timedelta

from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    origin_date = fields.Datetime()

    def _get_date_vals(self, name, product_id=None):
        if not name or len(name) < 5:
            return {}
        lot_number = name[:5]
        if not lot_number.isnumeric():
            return {}
        year, day = "20" + lot_number[:2], int(lot_number[2:])
        production = datetime.combine(
            date(int(year), 1, 1) + timedelta(days=day - 1),
            datetime.strptime("12:00", "%H:%M").time(),
        )
        if not product_id:
            return {"expiration_date": production.strftime("%Y-%m-%d %H:%M:%S")}
        product = self.env["product.product"].browse(product_id)
        if not product.use_expiration_date:
            return {}
        tmpl = product.product_tmpl_id
        exp = production + timedelta(days=tmpl.expiration_time)
        return {
            "origin_date": production.strftime("%Y-%m-%d %H:%M:%S"),
            "expiration_date": exp.strftime("%Y-%m-%d %H:%M:%S"),
            "use_date": (exp - timedelta(days=tmpl.use_time)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "removal_date": (exp - timedelta(days=tmpl.removal_time)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "alert_date": (exp - timedelta(days=tmpl.alert_time)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }

    def write(self, vals):
        if "name" in vals and "expiration_date" not in vals:
            unhandled = self.env[self._name]
            for lot in self:
                date_vals = lot._get_date_vals(vals["name"], lot.product_id.id)
                if date_vals:
                    lot.write({**vals, **date_vals})
                else:
                    unhandled |= lot
            if unhandled:
                return super().write(vals)
            return True
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res.write({"origin_date": fields.Datetime.now()})
        res._calculate_expiration_date()
        return res

    def _calculate_expiration_date(self):
        for lot in self:
            date_vals = lot._get_date_vals(lot.name, lot.product_id.id)
            if date_vals:
                lot.write(date_vals)

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
