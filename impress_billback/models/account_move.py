import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    billback_partner_id = fields.Many2one("res.partner", string="Billback Partner")
    billback_invoice_id = fields.Many2one("account.move", readonly=True, copy=False)
    billback_bill_id = fields.Many2one("account.move", readonly=True, copy=False)

    def action_billback(self):
        if not self.billback_partner_id:
            raise UserError(_("Please select Billback Partner"))
        elif self.billback_invoice_id:
            raise UserError(_("Billback invoice already created"))
        elif self.state in ["draft", "cancel"]:
            raise UserError(
                _("You can not create billback for a draft or cancelled invoice.")
            )
        elif self.move_type not in ["in_invoice", "entry"]:
            raise UserError(_(f"Cannot billback move of type {self.move_type}"))
        else:
            self.billback_invoice_id = (
                self.env["account.move"]
                .with_context(default_move_type="out_invoice")
                .create(
                    {
                        "partner_id": self.billback_partner_id.id,
                        "billback_bill_id": self.id,
                    }
                )
            )
            for line in self.line_ids:
                if line.price_total != 0:
                    self.env["account.move.line"].with_context(
                        default_move_id=self.billback_invoice_id.id
                    ).create(
                        {
                            "move_id": self.billback_invoice_id.id,
                            "name": line.name,
                            "quantity": line.quantity,
                            "price_unit": line.price_unit,
                        }
                    )

    def action_view_billback_invoice(self):
        return {
            "name": _("Billback Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.billback_invoice_id.id,
            "target": "current",
        }

    def action_view_billback_bill(self):
        return {
            "name": _("Billback Bill"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.billback_bill_id.id,
            "target": "current",
        }
