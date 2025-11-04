import logging

from odoo import _, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def button_unlock(self):
        if (
            self.env.user.has_group(
                "impress_purchase_customizations.can_bypass_po_locks"
            )
            or self.user_id == self.env.user
        ):
            return super().button_unlock()
        else:
            raise ValidationError(_("You cannot unlock another user's PO!"))
