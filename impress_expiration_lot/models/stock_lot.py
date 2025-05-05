import logging
from datetime import datetime, timedelta

from odoo import models

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
