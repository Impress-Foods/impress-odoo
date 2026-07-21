from datetime import date, datetime, timedelta

from odoo import api, models


class StockLot(models.Model):
    _inherit = "stock.lot"

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
        res._calculate_expiration_date()
        return res

    def _calculate_expiration_date(self):
        for lot in self:
            date_vals = lot._get_date_vals(lot.name, lot.product_id.id)
            if date_vals:
                lot.write(date_vals)
