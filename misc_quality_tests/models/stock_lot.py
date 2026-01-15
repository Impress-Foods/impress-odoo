from odoo import _, api, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    misc_test_ids = fields.One2many(
        string="Miscellaneous Tests",
        comodel_name="misc.test",
        inverse_name="lot_id",
    )

    misc_test_count = fields.Integer(compute="_compute_misc_test_count")

    @api.depends("misc_test_ids")
    def _compute_misc_test_count(self) -> None:
        for lot in self:
            lot.misc_test_count = len(lot.misc_test_ids)

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
