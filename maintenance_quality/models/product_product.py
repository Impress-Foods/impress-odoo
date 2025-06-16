import logging

from odoo import models
from odoo.tools import SQL

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def action_see_quality_control_points(self):
        res = super().action_see_quality_control_points()
        domain = res["domain"]
        domain.append(("control_point_type", "=", "stock"))
        res["domain"] = domain
        return res


class ProductProduct(models.Model):
    _inherit = "product.product"

    def action_see_quality_control_points(self):
        res = super().action_see_quality_control_points()
        domain = res["domain"]
        domain.append(("control_point_type", "=", "stock"))
        res["domain"] = domain
        return res

    def _count_quality_points(self):
        """Compute the count of all related quality points,
        which means quality points that have either
        the product in common, a product category parent
        of this product's category or no product/category
        set at all.
        """

        query = self.env["quality.point"]._where_calc(
            [("company_id", "=", self.env.company.id)]
        )
        self.env["quality.point"]._apply_ir_rules(query, "read")

        additional_where_clause = self._additional_quality_point_where_clause()
        if additional_where_clause:
            query.add_where(additional_where_clause)

        parent_category_ids = (
            [int(parent_id) for parent_id in self.categ_id.parent_path.split("/")[:-1]]  # type: ignore
            if self.categ_id
            else []
        )

        query.add_where(
            SQL(
                """
                    (
                        -- QP has at least one linked product and one is right
                        EXISTS (SELECT 1 FROM product_product_quality_point_rel rel WHERE rel.quality_point_id = quality_point.id AND rel.product_product_id = ANY(%s))
                        -- Or QP has at least one linked product category and one is right
                        OR EXISTS (SELECT 1 FROM product_category_quality_point_rel rel WHERE rel.quality_point_id = quality_point.id AND rel.product_category_id = ANY(%s))
                    )
                    OR (
                        -- QP has no linked products
                        NOT EXISTS (SELECT 1 FROM product_product_quality_point_rel rel WHERE rel.quality_point_id = quality_point.id)
                        -- And QP has no linked product categories
                        AND NOT EXISTS (SELECT 1 FROM product_category_quality_point_rel rel WHERE rel.quality_point_id = quality_point.id )
                    )
            """,  # noqa
                self.ids,
                parent_category_ids,
            )
        )

        rows = self.env.execute_query(query.select("id"))
        ids = [int(element[0]) for element in rows]
        qc_points = (
            self.env["quality.point"]
            .browse(ids)
            .filtered_domain([("control_point_type", "=", "stock")])
        )
        return len(qc_points)
