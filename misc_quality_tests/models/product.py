from odoo import _, api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    misc_test_count = fields.Integer(compute="_compute_misc_test_count")
    misc_test_ids = fields.Many2many("misc.test")

    @api.depends("misc_test_ids")
    def _compute_misc_test_count(self) -> None:
        for rec in self:
            rec.misc_test_count = len(rec.misc_test_ids)

    def action_open_misc_tests(self) -> dict:
        self.ensure_one()
        if self.misc_test_count == 1:
            action = {
                "name": _("Tests"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "misc.test",
                "res_id": self.misc_test_ids[0].id,
            }
        else:
            action = {
                "name": _("Tests"),
                "type": "ir.actions.act_window",
                "view_mode": "tree,form",
                "res_model": "misc.test",
                "domain": [("id", "in", [self.misc_test_ids.mapped("id")])],
            }

        return action
