from odoo import models


class QualityCheckWizard(models.TransientModel):
    _inherit = "quality.check.wizard"

    def do_na(self):
        self.ensure_one()
        self.current_check_id.do_na()
        return self.action_generate_next_window()
