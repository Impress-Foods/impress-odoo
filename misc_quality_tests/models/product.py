from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    misc_test_count = fields.Integer(compute="_compute_misc_test_count")
    misc_test_ids = fields.Many2many("misc.test")
    misc_test_target_ids = fields.One2many("misc.test", "product_id")

    shelf_life_change = fields.Text()

    @api.depends("misc_test_ids", "misc_test_target_ids")
    def _compute_misc_test_count(self) -> None:
        for rec in self:
            rec.misc_test_count = len(rec.misc_test_ids) + len(rec.misc_test_target_ids)

    def action_open_misc_tests(self) -> dict:
        self.ensure_one()
        if self.misc_test_count == 1:
            test = (
                self.misc_test_ids[0]
                if self.misc_test_ids
                else self.misc_test_target_ids[0]
            )
            action = {
                "name": self.env._("Tests"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "misc.test",
                "res_id": test.id,
            }

        else:
            action = {
                "name": self.env._("Tests"),
                "type": "ir.actions.act_window",
                "view_mode": "list,form",
                "res_model": "misc.test",
                "domain": [
                    (
                        "id",
                        "in",
                        (self.misc_test_ids + self.misc_test_target_ids).ids,
                    )
                ],
            }

        return action
