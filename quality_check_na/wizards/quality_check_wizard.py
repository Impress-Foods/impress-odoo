from odoo import fields, models


class QualityCheckWizard(models.TransientModel):
    _inherit = "quality.check.wizard"

    can_be_na = fields.Boolean(related="current_check_id.can_be_na")

    def do_na(self):
        self.ensure_one()
        self.current_check_id.do_na()
        return self.action_generate_next_window()
