from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _program_check_compute_points(self, programs):
        """
        Check for per-customer usage limit.
        """
        result = super()._program_check_compute_points(programs)
        for program in programs:
            # Skip if already has an error from super
            if "error" in result[program]:
                continue
            if (
                program.limit_usage_per_customer
                and self.partner_id
                and program._is_used_by_partner(self.partner_id, current_order=self)
            ):
                result[program] = {
                    "error": self.env._(
                        "This program has already been used by this customer."
                    )
                }
        return result

    def _try_apply_code(self, code):
        """
        Provide early feedback when a code is manually applied.
        """
        rule = self.env["loyalty.rule"].search(
            [
                ("mode", "=", "with_code"),
                ("code", "=", code),
                ("program_id.active", "=", True),
                ("program_id.limit_usage_per_customer", "=", True),
            ],
            limit=1,
        )
        program = rule.program_id

        if not program:
            coupon = self.env["loyalty.card"].search(
                [
                    ("code", "=", code),
                    ("program_id.active", "=", True),
                    ("program_id.limit_usage_per_customer", "=", True),
                ],
                limit=1,
            )
            program = coupon.program_id

        if (
            program
            and self.partner_id
            and program._is_used_by_partner(self.partner_id, current_order=self)
        ):
            return {
                "error": self.env._("This code has already been used by this customer.")
            }

        return super()._try_apply_code(code)
