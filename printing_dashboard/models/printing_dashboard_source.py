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

    def _label_quantity_for(
        self, target: models.Model
    ) -> tuple[float | None, models.Model, models.Model]:
        """Return the (quantity, uom, packaging uom) this source states.

        ``None`` means the source says nothing about this target at all, which
        is a different answer from zero of it.  ``packaging_uom`` is set only
        when the quantity was restated in a document packaging unit.  Sources
        that know a quantity override this method.
        """
        self.ensure_one()
        empty = self.env["uom.uom"]
        return None, empty, empty

    def _total_line_quantity_and_uom(
        self, lines: models.Model
    ) -> tuple[float, models.Model]:
        """Return the total quantity of ``lines`` and the unit it is stated in.

        A move line may carry its own unit -- a packaging or a seller's unit --
        so the quantities are converted to the first line's unit rather than
        adding unlike numbers.
        """
        if not lines:
            return 0.0, self.env["uom.uom"]
        uom = lines[0].product_uom_id
        return (
            sum(
                line.product_uom_id._compute_quantity(line.quantity, uom)
                for line in lines
            ),
            uom,
        )

    def _label_quantity_in_packaging_uom(
        self, quantity: float, uom: models.Model, moves: models.Model
    ) -> tuple[float, models.Model, models.Model]:
        """Return (quantity, uom, packaging uom) in the moves' document unit.

        A move created from a purchase or sale order carries the document unit
        in ``packaging_uom_id`` while its lines are recorded in the product's
        base unit.  A label should state the packaging count the operator
        handles, so the quantity is converted when every contributing move
        names the same packaging.  Mixed packaging units are left in their own
        unit rather than guessed at, and no packaging at all falls back to the
        normal quantity and unit.
        """
        empty = self.env["uom.uom"]
        if quantity is None or not uom or not moves:
            return quantity, uom, empty
        packaging_uom = moves[0].packaging_uom_id
        base_uom = moves[0].product_uom
        # ``packaging_uom_id`` defaults to the move's own unit.  It only names
        # the document unit when it differs from that unit; otherwise a line
        # deliberately recorded in a packaging would be converted back to base.
        if not packaging_uom or packaging_uom == base_uom:
            return quantity, uom, empty
        if any(
            move.packaging_uom_id != packaging_uom or move.product_uom != base_uom
            for move in moves
        ):
            return quantity, uom, empty
        return (
            uom._compute_quantity(quantity, packaging_uom),
            packaging_uom,
            packaging_uom,
        )

    def _label_batch_values(
        self, quantity: float, uom: models.Model, packaging_uom: models.Model
    ) -> dict[str, Any]:
        """Return the dashboard defaults for a label batch.

        A whole number of packages prints one label per package: 20 bins of
        10 kg become 20 labels stating 1 bin, rather than one label stating 20
        bins.  A fractional package count has no single quantity per label, so
        it keeps one label stating the fractional total.
        """
        if (
            packaging_uom
            and uom == packaging_uom
            and quantity
            and float(quantity).is_integer()
        ):
            return {
                "copies": int(quantity),
                "product_uom_qty": 1.0,
                "product_uom_id": packaging_uom,
            }
        return {
            "copies": 1,
            "product_uom_qty": quantity,
            "product_uom_id": uom,
        }

    def _label_print_values_for(self, target: models.Model) -> dict[str, Any]:
        """Return the label batch the source states for ``target``."""
        quantity, uom, packaging_uom = self._label_quantity_for(target)
        if quantity is None:
            return {}
        return self._label_batch_values(quantity, uom, packaging_uom)

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
