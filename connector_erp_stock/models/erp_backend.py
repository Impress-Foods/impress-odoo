from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class ERPBackend(models.Model):
    _inherit = "erp.backend"

    erp_product_ids = fields.One2many(
        comodel_name="erp.product", inverse_name="backend_id"
    )

    erp_product_count = fields.Integer(compute="_compute_erp_product_count")

    @api.depends("erp_product_ids")
    def _compute_erp_product_count(self):
        for rec in self:
            rec.erp_product_count = len(rec.erp_product_ids)

    def action_view_products(self):
        self.ensure_one()

        return {
            "res_model": "erp.product",
            "type": "ir.actions.act_window",
            "name": self.env._("Product mappings for %(name)s", name=self.name),
            "domain": Domain("id", "in", self.erp_product_ids.ids),
            "context": {"default_backend_id": self.id},
            "view_mode": "list",
        }

    def action_sync_products(self):
        self.ensure_one()
        self._sync_products()

    def _sync_products(self):
        for rec in self:
            method = getattr(self, f"_sync_products_{rec.backend_type}", None)
            if not method:
                raise ValidationError(
                    self.env._(
                        "Sync products method not implemented for "
                        "backend type %(type)s",
                        type=rec.backend_type,
                    )
                )

            res = method()
            success = "success" if res else "danger"
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": self.env._("Success"),
                    "message": self.env._("Products Synced!"),
                    "type": success,  # Options: 'success', 'danger', 'warning', 'info'
                    "sticky": False,  # True makes it stay until dismissed
                },
            }
