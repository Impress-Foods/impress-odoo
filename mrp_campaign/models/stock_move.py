from odoo import api, fields, models
from odoo.fields import Domain


class StockMove(models.Model):
    _inherit = "stock.move"

    sale_customer_ref = fields.Char(
        string="Customer Reference", related="sale_line_id.order_id.client_order_ref"
    )

    @api.model
    def _get_qty_to_fulfill_by_moves(self, moves) -> dict[int, float]:
        """Batch compute qty_to_fulfill for a recordset of moves.

        Returns a dict mapping move_id -> qty_to_fulfill (product_uom_qty - promised).
        """
        result = {m.id: m.product_uom_qty for m in moves}

        if not moves:
            return result

        domain = Domain("target_model", "=", "stock.move") & Domain(
            "target_id", "in", moves.ids
        )

        # returns [(target_id, promised_qty)]
        groups = self.env["mrp.campaign.demand.target"]._read_group(
            domain=domain,
            groupby=["target_id"],
            aggregates=["promised_qty:sum"],
            order="target_id",
        )

        for group in groups:
            target_id = group[0]
            if isinstance(target_id, list | tuple):
                target_id = target_id[0]
            if target_id in result:
                result[target_id] -= group[1]
        return result

    def _get_qty_to_fulfill(self) -> float:
        self.ensure_one()
        return self._get_qty_to_fulfill_by_moves(self)[self.id]
