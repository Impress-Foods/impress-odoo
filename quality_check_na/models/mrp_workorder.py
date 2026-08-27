from odoo import models
from odoo.exceptions import UserError


class MrpWorkOrder(models.Model):
    _inherit = "mrp.workorder"

    def verify_quality_checks(self):
        for check in self.check_ids:
            if check.quality_state in ["pass", "fail", "na"]:
                continue
            if check.test_type in [
                "register_consumed_materials",
                "register_byproducts",
                "instructions",
            ]:
                check.quality_state = "pass"
            else:
                raise UserError(
                    self.env._(
                        "You need to complete Quality Checks using the Shop "
                        "Floor before marking Work Order as Done."
                    )
                )
