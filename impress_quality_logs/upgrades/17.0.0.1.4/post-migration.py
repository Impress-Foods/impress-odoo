import logging

_logger = logging.getLogger(__name__)


def migrate(cr, registry):
    _logger.info("Starting 3-step signature migration for coding.log.")

    # Step 1: Rename 'signature' to a temporary name to avoid conflicts.
    _logger.info("Renaming 'signature' attachments to a temporary field.")
    cr.execute(
        """
        UPDATE ir_attachment
        SET res_field = 'operator_signature_temp_migration'
        WHERE
            res_model = 'coding.log' AND
            res_field = 'signature';
    """
    )
    _logger.info(f"{cr.rowcount} attachments moved to temporary field.")

    # Step 2: Move verifier signatures from 'verification_signature' to 'signature'.
    _logger.info("Renaming 'verification_signature' attachments to 'signature'.")
    cr.execute(
        """
        UPDATE ir_attachment
        SET res_field = 'signature'
        WHERE
            res_model = 'coding.log' AND
            res_field = 'verification_signature';
    """
    )
    _logger.info(f"{cr.rowcount} verifier signature attachments migrated.")

    # Step 3: Rename the temporary field to the final 'operator_signature'.
    _logger.info("Renaming temporary attachments to 'operator_signature'.")
    cr.execute(
        """
        UPDATE ir_attachment
        SET res_field = 'operator_signature'
        WHERE
            res_model = 'coding.log' AND
            res_field = 'operator_signature_temp_migration';
    """
    )
    _logger.info(f"{cr.rowcount} operator signature attachments migrated.")

    _logger.info("Signature migration for coding.log complete.")
