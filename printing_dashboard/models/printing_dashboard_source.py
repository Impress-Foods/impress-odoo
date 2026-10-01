from typing import Any

from odoo import api, models
from odoo.exceptions import UserError


class PrintingDashboardSource(models.AbstractModel):
    _name = "printing.dashboard.source"
    _description = "Printing dashboard source"

    def _get_print_dashboard_context(self) -> dict[str, Any]:
        """Return the normalized context used to open the dashboard."""
        self.ensure_one()
        return {
            "source_model": self._name,
            "source_id": self.id,
            "target": self,
        }

    def _get_print_dashboard_target_ids(self) -> dict[str, list[int]]:
        """Return the target records this source may legitimately print for.

        Keyed by model, so a caller never has to union records of different
        models (which is not a valid set operation, and whose ids would
        otherwise collide across tables).  An empty mapping means the source
        imposes no restriction.
        """
        self.ensure_one()
        return {}

    def _check_target_allowed(self, target_model: str, target: models.Model) -> None:
        """Refuse a target that does not belong to this source.

        The target picker lists every product and lot in the database, which
        makes it easy to retarget something unrelated and print a plausible
        label for the wrong record.  A source that knows its own candidates
        rejects anything else.
        """
        self.ensure_one()
        candidates = self._get_print_dashboard_target_ids()
        if not candidates:
            return
        allowed = candidates.get(target_model, [])
        if target.id not in allowed:
            raise UserError(
                self.env._(
                    "The selected target is not part of %(record)s. Pick one of "
                    "its own products or lots.",
                    record=self.display_name,
                )
            )

    @api.model
    def _resolve_target(self, context: dict[str, Any]) -> tuple[str, int, int]:
        """Return (target_model, product_id, lot_id) from an open context."""
        target = context.get("target")
        if isinstance(target, models.BaseModel) and target:
            if target._name == "stock.lot":
                return "stock.lot", target.product_id.id or False, target.id
            if target._name == "product.product":
                return "product.product", target.id, False
        return (
            context.get("target_model") or "product.product",
            context.get("product_id") or False,
            context.get("lot_id") or False,
        )

    def action_open_print_dashboard(self) -> dict[str, Any]:
        """Open the common dashboard for the current record."""
        return self.env["printing.dashboard"].open_from_source(self)
