import logging
from collections.abc import Callable

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord

_logger = logging.getLogger(__name__)

INVENTORY_TYPE = "costco_846_out"


class EdiBackend(models.Model):
    _inherit = "edi.backend"

    costco_product_count = fields.Integer(
        string="Costco products",
        compute="_compute_costco_product_count",
        groups="sales_team.group_sale_manager",
        help="Products bound to this backend, inactive ones included.",
    )

    def _compute_costco_product_count(self) -> None:
        bindings = self.env["edi.rithum.costco.product"].with_context(active_test=False)
        counts = dict(
            bindings._read_group(
                [("backend_id", "in", self.ids)], ["backend_id"], ["__count"]
            )
        )
        for backend in self:
            backend.costco_product_count = counts.get(backend, 0)

    def action_view_costco_products(self) -> dict:
        """Open the products bound to this backend, inactive ones too."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "edi_rithum_costco.action_costco_product"
        )
        action["domain"] = [("backend_id", "=", self.id)]
        action["context"] = {"default_backend_id": self.id, "active_test": False}
        return action

    def action_costco_send_inventory(self) -> dict:
        """Send the stock of every bound product, and tell the user how it went."""
        self.ensure_one()
        errors: list[str] = []
        record = self.costco_send_inventory(errors.append)
        failed = bool(errors)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Costco inventory"),
                "message": "; ".join(errors)
                or self.env._(
                    "The inventory was sent (%(name)s).", name=record.exchange_filename
                ),
                "type": "danger" if failed else "success",
                "sticky": failed,
            },
        }

    def costco_send_inventory(
        self, on_error: Callable[[str], None] | None = None
    ) -> EDIExchangeRecord:
        """Create an inventory record for this backend, generate it and send it."""
        self.ensure_one()
        record = self.create_record(INVENTORY_TYPE, {})
        record.x12_generate_send(on_error=on_error)
        return record

    @api.model
    def _cron_costco_send_inventory(self) -> None:
        """Scheduled action: send the Costco inventory of the Rithum backend."""
        backend = self.env.ref("edi_rithum.rithum_backend")
        errors: list[str] = []
        backend.costco_send_inventory(errors.append)
        for error in errors:
            _logger.warning("Costco inventory not sent: %s", error)

    def action_costco_bind_products(self) -> None:
        """Bind the products of every Costco order received through this backend."""
        self.ensure_one()
        lines = self.env["sale.order.line"].search(
            [
                ("costco_sku", "!=", False),
                ("order_id.origin_exchange_record_id.backend_id", "=", self.id),
            ]
        )
        if not lines:
            raise UserError(self.env._("No Costco order line was found."))
        self.env["edi.rithum.costco.product"].bind_order_lines(self, lines)
