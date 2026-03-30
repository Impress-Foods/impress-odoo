from odoo.upgrade import util


def migrate(cr, version):
    # remove LOMA related models
    util.remove_model(cr, "loma.log.line")
    util.remove_model(cr, "loma.log")
