from odoo import models
from odoo.exceptions import UserError
from odoo.fields import Domain


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        for move in self.filtered(lambda mv: mv.ref and mv.commercial_partner_id):
            move_domain = (
                Domain("commercial_partner_id", "=", move.commercial_partner_id.id)
                & Domain("ref", "=", move.ref)
                & Domain("move_type", "=", move.move_type)
            )
            matching_posted_move = self.search(
                move_domain & Domain("state", "=", "posted")
            )

            matching_in_progress = (self - move).filtered_domain(move_domain)

            matching_move = matching_posted_move + matching_in_progress

            if matching_move:
                raise UserError(
                    self.env._(
                        "Bill for client '%(client)s' with reference '%(ref)s' "
                        "already exists: %(bills)s",
                        client=move.partner_id.display_name,
                        ref=move.ref,
                        bills=matching_move.mapped("display_name"),
                    )
                )

        return super()._post(soft)
