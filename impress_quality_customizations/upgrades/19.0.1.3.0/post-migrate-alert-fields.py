from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Backfill the fields added to quality alerts in 19.0.1.3.0."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.cr.execute(
        "UPDATE quality_alert SET alert_type = 'quality' WHERE alert_type IS NULL"
    )

    env.cr.execute(
        "UPDATE quality_alert SET impact_on_product = 'no'"
        " WHERE impact_on_product IS NULL"
    )

    alerts = env["quality.alert"].with_context(active_test=False).search([])
    alerts._compute_product_uom_id()
    alerts._compute_origin_orders()
    env.flush_all()
