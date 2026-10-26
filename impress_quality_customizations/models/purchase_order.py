from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    quality_alert_ids = fields.One2many(
        "quality.alert",
        "purchase_order_id",
        string="Quality Alerts",
    )
    quality_alert_count = fields.Integer(compute="_compute_quality_alert_count")

    @api.depends("quality_alert_ids")
    def _compute_quality_alert_count(self) -> None:
        for order in self:
            order.quality_alert_count = len(order.quality_alert_ids)

    def action_view_quality_alerts(self) -> dict:
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "quality_control.quality_alert_action_check"
        )
        action["domain"] = [("purchase_order_id", "=", self.id)]
        action["context"] = {
            "default_purchase_order_id": self.id,
            "default_partner_id": self.partner_id.id,
        }
        product = self.order_line.product_id
        if len(product) == 1:
            action["context"].update(
                {
                    "default_product_id": product.id,
                    "default_product_tmpl_id": product.product_tmpl_id.id,
                }
            )
        action["views"] = [(False, "list"), (False, "form")]
        if self.quality_alert_count == 1:
            action["views"] = [(False, "form")]
            action["res_id"] = self.quality_alert_ids.id
        return action
