from collections import defaultdict

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    minimum_shelf_life = fields.Integer(related="partner_id.minimum_shelf_life")

    def action_print_online_label(self):
        self.ensure_one()
        return self.env.ref(
            "impress_stock_customizations.action_report_online_sale_label"
        ).report_action(self, config=False)

    def _get_packing_list_move_lines(self, package):
        """Return the done move lines contained in ``package``.

        Nested packages are included.
        """
        self.ensure_one()
        return self.move_line_ids.filtered(
            lambda line: line.result_package_id == package
            or line.package_history_id.outermost_dest_id == package
        )

    def _prepare_packing_list_lines(self, move_lines):
        """Group move lines by product and lot, computing gross and net weights."""
        grouped_lines = defaultdict(lambda: {"quantity": 0.0, "gross": 0.0, "net": 0.0})
        for line in move_lines:
            product = line.product_id
            quantity = line.product_uom_id._compute_quantity(
                line.quantity, product.uom_id, round=False
            )
            values = grouped_lines[(product.id, line.lot_id.id)]
            values.update(
                {"product": product, "lot": line.lot_id, "uom": product.uom_id}
            )
            values["quantity"] += quantity
            values["gross"] += product.weight * quantity
            values["net"] += product.net_weight * quantity
        return sorted(
            grouped_lines.values(),
            key=lambda values: (
                values["product"].display_name,
                values["lot"].name if values["lot"] else "",
            ),
        )

    def _get_packing_list_data(self):
        """Return the customs packing list structure for this picking."""
        self.ensure_one()
        packages = self.package_history_ids.filtered(
            lambda history: not history.parent_dest_id
        ).package_id

        sections = []
        has_lots = False
        total_gross = total_net = total_quantity = 0.0
        for package in packages:
            lines = self._prepare_packing_list_lines(
                self._get_packing_list_move_lines(package)
            )
            section_gross = package.weight
            section_net = sum(values["net"] for values in lines)
            section_quantity = sum(values["quantity"] for values in lines)
            has_lots = has_lots or any(values["lot"] for values in lines)
            sections.append(
                {
                    "package": package,
                    "lines": lines,
                    "gross": section_gross,
                    "net": section_net,
                    "quantity": section_quantity,
                }
            )
            total_gross += section_gross
            total_net += section_net
            total_quantity += section_quantity

        unpacked_lines = self._prepare_packing_list_lines(
            self.move_line_ids.filtered(lambda line: not line.result_package_id)
        )
        if unpacked_lines:
            has_lots = has_lots or any(values["lot"] for values in unpacked_lines)
            total_gross += sum(values["gross"] for values in unpacked_lines)
            total_net += sum(values["net"] for values in unpacked_lines)
            total_quantity += sum(values["quantity"] for values in unpacked_lines)

        return {
            "sections": sections,
            "unpacked_lines": unpacked_lines,
            "has_lots": has_lots,
            "total_packages": len(packages),
            "total_gross": total_gross,
            "total_net": total_net,
            "total_quantity": total_quantity,
        }
