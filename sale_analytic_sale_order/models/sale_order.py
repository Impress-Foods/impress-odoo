from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Analytic Account",
        copy=False,
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
