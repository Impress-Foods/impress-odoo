from odoo import models


class ProductProduct(models.Model):
    _name = "product.product"
    _inherit = ["printing.dashboard.source", "product.product"]


class ProductTemplate(models.Model):
    _name = "product.template"
    _inherit = ["printing.dashboard.source", "product.template"]

    def _get_print_dashboard_context(self):
        context = super()._get_print_dashboard_context()
        context["target"] = self.product_variant_id
        return context

    def _get_print_dashboard_target_ids(self) -> dict[str, list[int]]:
        self.ensure_one()
        return {"product.product": self.product_variant_ids.ids}


class StockLot(models.Model):
    _name = "stock.lot"
    _inherit = ["printing.dashboard.source", "stock.lot"]

    def _get_print_dashboard_target_ids(self) -> dict[str, list[int]]:
        self.ensure_one()
        return {"product.product": self.product_id.ids, "stock.lot": self.ids}


class StockMove(models.Model):
    _name = "stock.move"
    _inherit = ["printing.dashboard.source", "stock.move"]

    def _get_print_dashboard_context(self):
        self.ensure_one()
        context = super()._get_print_dashboard_context()
        target = self.product_id
        if len(self.move_line_ids) == 1 and self.move_line_ids.lot_id:
            target = self.move_line_ids.lot_id
        context.update(
            {
                "target": target,
                "product_uom_qty": self.product_uom_qty,
                "product_uom_id": self.product_uom,
            }
        )
        return context

    def _get_print_dashboard_target_ids(self) -> dict[str, list[int]]:
        self.ensure_one()
        return {
            "product.product": self.product_id.ids,
            "stock.lot": self.move_line_ids.lot_id.ids,
        }


class StockMoveLine(models.Model):
    _name = "stock.move.line"
    _inherit = ["printing.dashboard.source", "stock.move.line"]

    def _get_print_dashboard_context(self):
        self.ensure_one()
        context = super()._get_print_dashboard_context()
        target = self.lot_id or self.product_id
        context.update(
            {
                "target": target,
                "product_uom_qty": self.quantity,
                "product_uom_id": self.product_uom_id,
            }
        )
        return context

    def _get_print_dashboard_target_ids(self) -> dict[str, list[int]]:
        self.ensure_one()
        return {"product.product": self.product_id.ids, "stock.lot": self.lot_id.ids}


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["printing.dashboard.source", "stock.picking"]

    def _get_print_dashboard_context(self):
        self.ensure_one()
        context = super()._get_print_dashboard_context()
        # A single move narrows to its lot or product.  Anything else leaves
        # the target empty so the operator chooses, instead of defaulting to
        # the transfer and offering them a packing slip.
        target = self.env["stock.lot"]
        if len(self.move_ids) == 1:
            move = self.move_ids
            lots = move.move_line_ids.lot_id
            target = lots if len(lots) == 1 else move.product_id
        context["target"] = target
        if target:
            quantity, uom = self._label_quantity_for(target)
            if quantity:
                context["product_uom_qty"] = quantity
            if uom:
                context["product_uom_id"] = uom
        return context

    def _label_quantity_for(self, target) -> tuple:
        """Return the (quantity, uom) this transfer states for ``target``.

        A quantity of ``None`` means the transfer says nothing about this target
        at all, which is a different answer from zero of it: a lot this transfer
        received none of has to state zero, or the dashboard would go on showing
        whatever the previous target said.
        """
        self.ensure_one()
        if not target:
            return None, self.env["uom.uom"]
        if target._name == "stock.lot":
            lines = self.move_ids.move_line_ids.filtered(
                lambda line, target=target: line.lot_id == target
            )
            if not lines:
                return None, self.env["uom.uom"]
            return sum(lines.mapped("quantity")), lines[0].product_uom_id
        moves = self.move_ids.filtered(
            lambda move, target=target: move.product_id == target
        )
        if not moves:
            return None, self.env["uom.uom"]
        return sum(moves.mapped("product_uom_qty")), moves[0].product_uom

    def _get_print_dashboard_target_ids(self) -> dict[str, list[int]]:
        """Only this transfer's own lots and products are valid targets."""
        self.ensure_one()
        return {
            "product.product": self.move_ids.product_id.ids,
            "stock.lot": self.move_ids.move_line_ids.lot_id.ids,
        }


class MrpProduction(models.Model):
    _name = "mrp.production"
    _inherit = ["printing.dashboard.source", "mrp.production"]

    def _get_print_dashboard_context(self):
        self.ensure_one()
        context = super()._get_print_dashboard_context()
        target = self.product_id
        context.update(
            {
                "target": target,
                "product_uom_qty": self.product_uom_qty,
                "product_uom_id": self.product_uom_id,
            }
        )
        return context


class MrpWorkorder(models.Model):
    _name = "mrp.workorder"
    _inherit = ["printing.dashboard.source", "mrp.workorder"]

    def _get_print_dashboard_context(self):
        self.ensure_one()
        context = super()._get_print_dashboard_context()
        lots = self.finished_lot_ids
        target = lots[:1] if len(lots) == 1 else self.product_id
        if len(lots) > 1:
            target = self.env["stock.lot"]
        context.update(
            {
                "target": target,
                "product_uom_qty": self.qty_producing or self.qty_production,
                "product_uom_id": self.product_uom_id,
            }
        )
        return context

    def _get_print_dashboard_target_ids(self) -> dict[str, list[int]]:
        """Only this work order's own lots and product are valid targets."""
        self.ensure_one()
        return {
            "product.product": self.product_id.ids,
            "stock.lot": self.finished_lot_ids.ids,
        }
