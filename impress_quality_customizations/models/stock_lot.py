# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import ast

from odoo import api, fields, models
from odoo.fields import Domain


class StockLot(models.Model):
    _inherit = "stock.lot"

    recursive_check_qty = fields.Integer(
        string="Checks (Tree)",
        compute="_compute_recursive_check_qty",
        groups="quality.group_quality_user",
        help="Quality checks on this lot and, recursively, on every lot that went "
        "into the productions it came from.",
    )

    @api.depends_context("company")
    def _compute_recursive_check_qty(self) -> None:
        for lot in self:
            lot.recursive_check_qty = self.env["quality.check"].search_count(
                Domain.AND(
                    [
                        lot._get_recursive_quality_check_domain(),
                        [("company_id", "=", self.env.company.id)],
                    ]
                )
            )

    def action_open_recursive_quality_checks(self) -> dict:
        """Open the checks of the whole production tree."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "quality_control.quality_check_action_production_lot"
        )

        base_domain = ast.literal_eval(action["domain"]) if action["domain"] else []
        action["domain"] = Domain.AND(
            [base_domain, self._get_recursive_quality_check_domain()]
        )
        return action

    def _get_recursive_quality_check_domain(self) -> Domain:
        """Checks of this lot's production tree, upstream, however deep.
        :return: domain matching the checks of the tree
        """
        lot_ids = self._get_recursive_lot_ids()
        production_ids = self._get_recursive_production_ids(lot_ids)
        component_move_ids = self._get_recursive_component_move_ids(production_ids)
        picking_ids = self._get_recursive_picking_ids(lot_ids)
        return Domain.OR(
            [
                # Checks on the tree's lots: on the lot itself, per quantity, and on
                # the move lines that carry the lot.
                Domain("lot_ids", "in", sorted(lot_ids)),
                Domain("lot_line_id", "in", sorted(lot_ids)),
                Domain("move_line_id.lot_id", "in", sorted(lot_ids)),
                # Checks done during the productions: on the order, on its
                # operations, and on the components they consumed.
                Domain("production_id", "in", sorted(production_ids)),
                Domain("workorder_id.production_id", "in", sorted(production_ids)),
                Domain("move_id", "in", sorted(component_move_ids)),
                # Checks on the receipts and the shipments of the tree's lots.
                Domain("picking_id", "in", sorted(picking_ids)),
                Domain("move_line_id.move_id.picking_id", "in", sorted(picking_ids)),
            ]
        )

    def _get_recursive_lot_ids(self) -> set[int]:
        """Ids of this lot and of every lot upstream of it, however deep.

        :return: ids of the lots of the tree, including this one
        """
        seen_lot_ids = set(self.ids)
        seen_production_ids: set[int] = set()
        frontier = set(self.ids)
        while frontier:
            production_ids = (
                self._get_recursive_production_ids(frontier) - seen_production_ids
            )
            if not production_ids:
                break
            seen_production_ids |= production_ids
            frontier = (
                self._get_recursive_component_lot_ids(production_ids) - seen_lot_ids
            )
            seen_lot_ids |= frontier
        return seen_lot_ids

    @api.model
    def _get_recursive_production_ids(self, lot_ids: set[int]) -> set[int]:
        """Productions that made these lots.

        :param lot_ids: ids of the lots to look up
        :return: ids of the productions, empty when there is nothing to look up
        """
        if not lot_ids:
            return set()
        productions = self.env["mrp.production"].search(
            [("lot_producing_ids", "in", sorted(lot_ids))]
        )
        move_lines = self.env["stock.move.line"].search(
            [("lot_id", "in", sorted(lot_ids)), ("move_id.production_id", "!=", False)]
        )
        return set(productions.ids) | set(move_lines.move_id.production_id.ids)

    @api.model
    def _get_recursive_component_lot_ids(self, production_ids: set[int]) -> set[int]:
        """Tracked lots consumed by these productions.

        :param production_ids: ids of the productions to walk down from
        :return: ids of the component lots
        """
        if not production_ids:
            return set()
        productions = self.env["mrp.production"].browse(sorted(production_ids))
        return set(productions.move_raw_ids.move_line_ids.lot_id.ids)

    @api.model
    def _get_recursive_component_move_ids(self, production_ids: set[int]) -> set[int]:
        """Raw moves of these productions, which carry the component checks.

        :param production_ids: ids of the productions
        :return: ids of their component moves
        """
        if not production_ids:
            return set()
        productions = self.env["mrp.production"].browse(sorted(production_ids))
        return set(productions.move_raw_ids.ids)

    @api.model
    def _get_recursive_picking_ids(self, lot_ids: set[int]) -> set[int]:
        """Transfers these lots went through, cancelled ones excepted.

        :param lot_ids: ids of the lots of the tree
        :return: ids of their transfers
        """
        if not lot_ids:
            return set()
        move_lines = self.env["stock.move.line"].search(
            [("lot_id", "in", sorted(lot_ids))]
        )
        pickings = move_lines.move_id.picking_id.filtered(
            lambda picking: picking.state != "cancel"
        )
        return set(pickings.ids)
