from odoo.tools import SQL
from odoo.upgrade import util


def studio_to_base(cr, model: str, field: str) -> None:
    query = SQL(
        """
        UPDATE ir_model_fields
        SET state = 'base'
        WHERE name = %(field)s
            AND model = %(model)s
            AND state = 'manual'
        """,
        field=field,
        model=model,
    )
    cr.execute(query)


def migrate(cr, version):
    util.move_field_to_module(
        cr, "quality.check", "x_signature", "quality", "impress_quality_customizations"
    )
    studio_to_base(cr, "quality.check", "x_signature")
    util.rename_field(cr, "quality.check", "x_signature", "signature")

    util.move_field_to_module(
        cr, "quality.point", "x_is_ccp", "quality", "impress_quality_customizations"
    )
    studio_to_base(cr, "quality.point", "x_is_ccp")
    util.rename_field(cr, "quality.point", "x_is_ccp", "is_ccp")
