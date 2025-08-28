import ast
import logging
import typing
from datetime import date, datetime, time

from dateutil.relativedelta import FR, MO, SA, SU, TH, TU, WE, relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.base.models.res_currency import Currency
from odoo.addons.base.models.res_partner import Partner
from odoo.addons.sale_management.models.sale_order import SaleOrder
from odoo.addons.sale_management.models.sale_order_line import SaleOrderLine

from .warehouse_quant_group import (
    QuantHistoryGroup,
)

_logger = logging.getLogger(__name__)

weekdays = (MO, TU, WE, TH, FR, SA, SU)


class WarehouseBillingConfig(models.Model):
    _name = "warehouse.billing.config"
    _description = "Warehouse Billing Configuration"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    partner_id = fields.Many2one("res.partner", string="Customer", required=True)
    warehouse_id = fields.Many2one("stock.warehouse", required=True)
    billing_product_id = fields.Many2one(
        "product.product",
        string="Service Product",
        domain=[("type", "=", "service")],
        help="Product used for billing the warehouse space",
        required=True,
    )

    rate = fields.Monetary(string="Rate per unit", required=True)
    flat_fee = fields.Monetary(string="Monthly Flat Fee")
    base_qty = fields.Float(string="Base Quantity", default="0.0")

    billing_cycle = fields.Selection(
        [("monthly", "Monthly"), ("weekly", "Weekly"), ("daily", "Daily")],
        default="monthly",
        required=True,
    )

    bill_last_day_month = fields.Boolean(string="Bill Last Day of Month")
    billing_day_month = fields.Integer(
        string="Billing Day of Month",
        default=1,
        help="Day of the month when the invoice should be generated",
    )

    billing_day_week = fields.Integer(
        string="Billing Day of Week",
        default=1,
        help="Day of the week when the invoice should be generated",
    )

    measurement_type = fields.Selection(
        [
            ("cubic", "Cubic Meters"),
            ("square", "Square Meters"),
            ("pallet", "Pallet Spaces"),
        ],
        default="pallet",
        required=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    filter_domain = fields.Char(
        string="Domain", help="Domain to filter the warehouse space usage records"
    )
    grace_period = fields.Integer(default=0)

    last_invoice_date = fields.Date(default=fields.Date.context_today)
    next_planned_invoice_date = fields.Date(
        store=True,
        compute="_compute_next_planned_invoice_date",
    )

    bill_seperately = fields.Boolean(default=False)

    @api.depends(
        "last_invoice_date",
        "billing_cycle",
        "billing_day_month",
        "billing_day_week",
        "bill_last_day_month",
    )
    def _compute_next_planned_invoice_date(self) -> None:
        for record in self:
            match record.billing_cycle:
                case "daily":
                    record.next_planned_invoice_date = (
                        record.last_invoice_date + relativedelta(days=1)
                    )
                case "weekly":
                    record.next_planned_invoice_date = (
                        record.last_invoice_date
                        + relativedelta(
                            days=1, weekday=weekdays[record.billing_day_week - 1](+1)
                        )
                    )
                case "monthly":
                    if record.bill_last_day_month:
                        this_month = record.last_invoice_date + relativedelta(
                            months=2, day=1, days=-1
                        )
                        if this_month <= record.last_invoice_date:
                            record.next_planned_invoice_date = (
                                this_month + relativedelta(months=1)
                            )
                        else:
                            record.next_planned_invoice_date = this_month
                    else:
                        this_month = record.last_invoice_date + relativedelta(
                            day=record.billing_day_month
                        )
                        if this_month <= record.last_invoice_date:
                            record.next_planned_invoice_date = (
                                this_month
                                + relativedelta(months=1, day=record.billing_day_month)
                            )
                        else:
                            record.next_planned_invoice_date = this_month
                case _:
                    pass

    @api.constrains("billing_day_month")
    def _check_billing_day_month(self) -> None:
        for record in self:
            if record.billing_day_month < 1 or record.billing_day_month > 31:
                raise ValidationError(_("Billing day must be between 1 and 31."))

    @api.constrains("billing_day_week")
    def _check_billing_day_week(self) -> None:
        for record in self:
            if record.billing_day_week < 1 or record.billing_day_week > 7:
                raise ValidationError(_("Billing day must be between 1 and 7."))

    @api.onchange("partner_id")
    def _onchange_partner_id(self) -> None:
        if self.partner_id and not self.name:
            self.name = f"{self.partner_id.name}'s Warehouse Billing Configuration"

    def get_filter_domain(self) -> list:
        return ast.literal_eval(self.filter_domain) if self.filter_domain else []

    # Model method to allow to bill a whole recordset simultaneously
    # When called with a recordset, a single SO will be created for the whole recordset
    # With each config in the recordset resulting in a sale order line
    @api.model
    def bill_config(self, configs) -> SaleOrder:  # noqa C901
        current_date: date = typing.cast(
            date, self.env.context.get("warehouse_billing_date")
        )

        partner_id: Partner = configs[0].partner_id
        sale_order_lines_vals: dict[int, dict] = {}

        # Check if currencies for all config match
        currencies: set[Currency] = set(
            [currency.id for currency in configs.mapped("currency_id")]
        )

        if len(currencies) != 1:
            raise UserError(_("Currencies for all configs must match."))
        currency_id: Currency = currencies.pop()

        sale_order_id: SaleOrder = self.env["sale.order"]
        sale_order_lines: dict[WarehouseBillingConfig, SaleOrderLine] = {}

        groups: dict[WarehouseBillingConfig, QuantHistoryGroup] = {}

        # Generate a Quant History Group for each config
        for config in configs:
            start_date: date = config.last_invoice_date + relativedelta(days=1)
            end_date: date = min(config.next_planned_invoice_date, current_date)
            dates: tuple[date, date] = (start_date, end_date)

            sale_order_lines[config.id] = self.env["sale.order.line"]

            uoms: dict[str, str] = {
                "cubic": "m³ day",
                "square": "m² day",
                "pallet": "pallets day",
            }
            uom: str | None = uoms.get(config.measurement_type, "pallets day")

            # Check if we already have a quant group for the given dates and config
            existing_group: QuantHistoryGroup = self.env[
                "warehouse.quant.group"
            ].search(
                [
                    ("date_from", "=", dates[0]),
                    ("date_to", "=", dates[1]),
                    ("config_id", "=", config.id),
                    ("partner_id", "=", config.partner_id.id),
                ]
            )

            # Handle existig group
            if existing_group:
                # If we have multiple matching group, we don't know which one to use.
                # We will just skip this config
                if len(existing_group) != 1:
                    _logger.warning(
                        f"Multiple quant groups found for {config.partner_id.name}"
                        f" from {dates[0]} to {dates[1]}. Skipping"
                    )
                    continue

                # We check if the group is currently linked to an SO. If so,
                # we will use that SO for the whole recordset
                if existing_group.sale_order_id:
                    # If we don't currently have an SO selected,
                    # we'll use the one from the existing group
                    if not sale_order_id:
                        sale_order_id = existing_group.sale_order_id
                    # If we already have an SO selected, but there is a conflict
                    # with the existing group, throw an error.
                    # We don't know which one to use
                    elif sale_order_id != existing_group.sale_order_id:
                        raise UserError(_("All configs must have the same sale order."))

                # We check if the group is currently linked to an SO line.
                # If so, we will use that SO line for this config
                if existing_group.sale_order_line_id:
                    sale_order_lines[config.id] = existing_group.sale_order_line_id
                    _logger.warning(f"Existing quant group found: {existing_group}")

            # Set up the search domain for the quant history
            quant_history_domain: list = (
                config.get_filter_domain()
                + [("date", ">=", dates[0]), ("date", "<=", dates[1])]
                + [("group_id", "=", False)]
            )

            # Get all quant_history records for the given date and
            # respecting the config's domain
            quant_history = self.env["warehouse.quant.history"].search(
                quant_history_domain
            )

            if existing_group:
                quant_history += existing_group.quant_history_ids

            if not quant_history and config.base_qty == 0 and config.flat_fee == 0:
                _logger.warning(
                    f"No records found for {config.name}"
                    f" from {dates[0]} to {dates[1]}. Skipping"
                )
                continue

            # Create or update the quant group
            if not existing_group:
                group = self.env["warehouse.quant.group"].create(
                    {
                        "date_from": start_date,
                        "date_to": end_date,
                        "config_id": config.id,
                        "partner_id": config.partner_id.id,
                        "quant_history_ids": [
                            (fields.Command.link(record.id)) for record in quant_history
                        ],
                    }
                )
            else:
                group = existing_group
                group.write(
                    {
                        "quant_history_ids": [
                            (fields.Command.link(record.id)) for record in quant_history
                        ],
                    }
                )

            days_elapsed: int = (
                (end_date - start_date).days if config.billing_cycle != "daily" else 1
            )

            total_usage: float = group.get_usage() + config.base_qty * days_elapsed
            total_amount: float = total_usage * config.rate + config.flat_fee

            if total_amount <= 0:
                _logger.warning(
                    f"Total is less than or equal to 0 for {config.name}"
                    f" from {dates[0]} to {dates[1]}. Skipping"
                )
                if sale_order_lines[config.id]:
                    sale_order_lines[config.id].unlink()
                continue

            description = _(
                f"""Warehouse Space Usage: {dates[0]} to {dates[1]}\n"""
                f"""Category: {config.name}\n"""
                f"""Cycle: {config.billing_cycle}\n"""
                f"""Total Usage: {total_usage} {uom}\n"""
                f"""Rate: {config.rate:.2f} per {uom}"""
            )

            sale_order_line_vals = {
                "product_id": config.billing_product_id.id,
                "product_uom_qty": 1,
                "price_unit": total_amount,
                "name": description,
            }

            groups[config.id] = group

            if not sale_order_lines[config.id]:
                sale_order_lines_vals[config.id] = sale_order_line_vals
            else:
                sale_order_lines[config.id].write(sale_order_line_vals)

            config.last_invoice_date = end_date

        so_date: datetime = datetime.combine(
            configs[0].last_invoice_date, time(hour=23, minute=0)
        )
        if len(sale_order_lines_vals) > 0 and not sale_order_id:
            sale_order_id: SaleOrder = self.env["sale.order"].create(  # type: ignore
                {
                    "partner_id": partner_id.id,
                    "currency_id": currency_id,
                    "date_order": so_date,
                    "origin": f"Warehousing Fees - {current_date}",
                }
            )

        # We should always have a sale_order_id here, but check for safety
        if sale_order_id:
            # Go over all our configs to finish linking and create the sale_order_lines
            for config in configs:
                if config.id in sale_order_lines_vals:
                    vals = sale_order_lines_vals[config.id]
                    vals["order_id"] = sale_order_id.id
                    sale_order_line_id = self.env["sale.order.line"].create(
                        sale_order_lines_vals[config.id]
                    )
                    groups[config.id].write(
                        {"sale_order_line_id": sale_order_line_id.id}
                    )
                    sale_order_lines[config.id] = sale_order_line_id

            sol_ids = [sol.id for sol in sale_order_lines.values()]
            sale_order_id.update(
                {
                    "order_line": sol_ids,
                }
            )

            if sale_order_id.state not in ["sale"]:
                sale_order_id.action_confirm()
                sale_order_id.write({"date_order": so_date})

        return sale_order_id
