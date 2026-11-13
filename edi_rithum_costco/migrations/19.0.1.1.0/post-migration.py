def migrate(cr, version):
    """Orders keep their retailer: copy it from the file that created them."""
    cr.execute(
        """
        UPDATE sale_order so
           SET rithum_partner_id = er.rithum_partner_id
          FROM edi_exchange_record er
         WHERE so.origin_exchange_record_id = er.id
           AND er.rithum_partner_id IS NOT NULL
           AND so.rithum_partner_id IS NULL
        """
    )
