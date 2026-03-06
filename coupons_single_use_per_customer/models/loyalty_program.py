from odoo import fields, models


class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"

    limit_usage_per_customer = fields.Boolean(
        string="Limit usage per customer",
        help="If checked, each customer can only use this program once, "
        "even if the total usage is unlimited.",
    )

    def _is_used_by_partner(self, partner, current_order=None):
        """
        Check if the program has already been used by the given partner or email.
        Checks main partner, billing partner, and shipping partner emails.
        """
        self.ensure_one()
        if not partner:
            return False

        # Do not block the public user (base for guest checkout)
        public_user = self.env.ref("base.public_user", raise_if_not_found=False)
        if public_user and partner == public_user.partner_id:
            return False

        # Search for confirmed orders with rewards from this program
        domain = [
            ("state", "in", ("sale", "done")),
            ("order_line.reward_id.program_id", "=", self.id),
        ]
        if current_order:
            domain.append(("id", "!=", current_order.id))

        # 1. Check by commercial partner
        partner_domain = domain + [
            ("partner_id.commercial_partner_id", "=", partner.commercial_partner_id.id)
        ]
        if self.env["sale.order"].search_count(partner_domain) > 0:
            return True

        # 2. Collect all emails to check (main, billing, shipping)
        # Normalize emails (strip whitespace and lowercase) to prevent bypass
        emails = set()
        if partner.email:
            emails.add(partner.email.lower().strip())
        if current_order:
            if current_order.partner_invoice_id.email:
                emails.add(current_order.partner_invoice_id.email.lower().strip())
            if current_order.partner_shipping_id.email:
                emails.add(current_order.partner_shipping_id.email.lower().strip())

        if emails:
            # Build domain: for each email, check all 3 address fields with OR
            email_domain = domain
            for email in emails:
                email_domain += [
                    "|",
                    "|",
                    ("partner_id.email", "=ilike", email),
                    ("partner_invoice_id.email", "=ilike", email),
                    ("partner_shipping_id.email", "=ilike", email),
                ]
            if self.env["sale.order"].search_count(email_domain) > 0:
                return True

        return False
