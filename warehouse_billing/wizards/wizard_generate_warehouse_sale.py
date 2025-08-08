import logging
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.warehouse_billing_config import (
    WarehouseBillingConfig,
)

_logger = logging.getLogger(__name__)


class GenerateWarehouseSaleOrder(models.TransientModel):
    _name = "wizard.generate.warehouse.sale.order"
    _description = "Generate Warehouse Space Sale Order"

    name = fields.Char(string="Reference", readonly=True, copy=False)
    partner_id = fields.Many2one("res.partner", string="Customer")
    run_date = fields.Date(default=fields.Date.context_today)

    @api.model
    def end_of_month(self, dt: date) -> bool:
        todays_month = dt.month
        tomorrows_month = (dt + timedelta(days=1)).month
        return todays_month != tomorrows_month

    @api.model
    def group_by_partner(self, configs) -> dict:
        grouped_configs = {}  # type: ignore
        for config in configs:
            if config.partner_id not in grouped_configs:
                grouped_configs[config.partner_id] = []
            grouped_configs[config.partner_id].append(config.id)
        for config in grouped_configs:
            grouped_configs[config] = self.env["warehouse.billing.config"].browse(
                grouped_configs[config]
            )
        return grouped_configs

    @api.model
    def get_configs_to_bill(self, check_date: date):
        config = self.env["warehouse.billing.config"]

        # Search for all configs where their next planned
        #  invoice date is today or in the past
        config_list = config.search(
            [("active", "=", True), ("next_planned_invoice_date", "<=", check_date)]
        )
        return config_list

    @api.model
    def generate_sale_order_line_values(self, config, group, today):
        if not config.billing_product_id:
            raise UserError(_("No billing product defined for %s.") % config.name)

        # If we have an empty group, we should create a sale order
        #  with only the flat fee and base_qtys
        if len(group) != 0:
            sale_order_line_vals = group.generate_sale_order_line_values()
        else:
            if config.measurement_type == "cubic":
                uom = "m³"
            elif config.measurement_type == "square":
                uom = "m²"
            else:  # pallet
                uom = "pallets"

            dates = config.get_billing_dates(today)
            description = _(
                f"""Warehouse Space Usage: {dates[0]} to {dates[1]}\n"""
                f"""Category: {config.name}\n"""
                f"""Cycle: {config.billing_cycle}\n"""
                f"""Total Usage: {config.base_qty} {uom}\n"""
                f"""Rate: {config.rate:.2f} per {uom}"""
            )
            total_amount = config.base_qty * config.rate + config.flat_fee
            sale_order_line_vals = {
                "product_id": config.billing_product_id.id,
                "name": description,
                "product_uom_qty": 1,
                "price_unit": total_amount,
                "currency_id": config.currency_id.id,
            }

        return sale_order_line_vals

    def action_generate_sale_order(self, configs):
        # We get all the configs for a partner
        # We want to create a single Sale Order for all the configs for a single partner
        # We want to create a single Sale Order Line for each of the configs

        self.ensure_one()

        today = self.run_date

        if not configs:
            raise UserError(_("No billing configurations found."))
        if not all(configs.mapped("billing_product_id")):
            raise UserError(
                _("Some billing configurations do not have a billing product defined.")
            )

        # Check if currencies for all config match
        currencies = set([currency.id for currency in configs.mapped("currency_id")])

        if len(currencies) != 1:
            raise UserError(_("Currencies for all configs must match."))
        currency_id = currencies.pop()

        # Generate a Quant History Group for each config
        quant_history = {
            config: self.env["warehouse.quant.group"].group_quant_history(config, today)
            for config in configs
        }

        # Check for empty recordsets
        quant_history = {
            config: group
            for config, group in quant_history.items()
            if len(group) != 0 or config.base_qty
        }

        # Check for groups with no sale_order_id
        quant_history = {
            config: group
            for config, group in quant_history.items()
            if not group.sale_order_id
        }

        if quant_history == {}:
            return

        # If we have quant groups, we can proceed to create the sale order
        # This prevents the creation of empty sale orders

        # We should get a dictionary of configs and their quant.groups
        # Each quant.group / config is a single sale order line
        # All the quant.group / configs should be in a single sale order

        sale_order_vals = {
            "partner_id": self.partner_id.id,
            "origin": f"Warehousing fees - {today}",
            "date_order": fields.Date.today(),
            "currency_id": currency_id,
        }

        sale_order = self.env["sale.order"].create(sale_order_vals)
        sale_order_lines = []

        # Generate sale order line for each group
        for config, group in quant_history.items():
            sale_order_line_vals = self.generate_sale_order_line_values(
                config, group, today
            )
            sale_order_line_vals.update({"order_id": sale_order.id})
            sale_order_line = self.env["sale.order.line"].create(sale_order_line_vals)
            sale_order_lines.append(fields.Command.link(sale_order_line.id))

            group.write(
                {
                    "sale_order_id": sale_order.id,
                    "sale_order_line_id": sale_order_line.id,
                }
            )
            group.quant_history_ids.write({"invoiced": True})

        sale_order.write(
            {
                "order_line": sale_order_lines,
            }
        )

    @api.model
    def group_configs(
        self, configs: WarehouseBillingConfig
    ) -> dict[list | int, WarehouseBillingConfig]:
        i = 0
        grouped_configs = {}
        for config in configs:
            if config.bill_seperately:
                grouped_configs[i] = config
                i += 1
            else:
                key = [config.partner_id, config.billing_cycle, config.warehouse_id]
                if config.bill_last_day_month:
                    key.append(config.bill_last_day_month)
                elif config.billing_day_month != 0:
                    key.append(config.billing_day_month)
                elif config.billing_day_week != 0:
                    key.append(config.billing_day_week)

                key = tuple(key)  # type: ignore
                if key not in grouped_configs:
                    grouped_configs[key] = config  # type: ignore
                else:
                    grouped_configs[key] += config  # type: ignore
        return grouped_configs  # type: ignore

    @api.model
    def generate_sale_orders(self, current_date: date | None = None):
        """Cron job to automatically generate sale orders"""
        if current_date is None:
            current_date = datetime.today().date()

        config_model = self.env["warehouse.billing.config"]

        # Get all active billing configurations due for invoicing
        configs = self.get_configs_to_bill(current_date)

        while len(configs) != 0:
            sale_orders = self.env["sale.order"]
            grouped_configs = self.group_configs(configs)
            _logger.warning(grouped_configs)
            for key in grouped_configs:
                sale_orders += config_model.with_context(
                    warehouse_billing_date=date
                ).bill_config(grouped_configs[key])

            configs = self.get_configs_to_bill(current_date)

            if not sale_orders:
                break

        return
