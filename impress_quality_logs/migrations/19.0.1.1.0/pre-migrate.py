"""Refuse to upgrade while a production has more than one log of a type.

19.0.1.1.0 adds UNIQUE(production_id) on every log model. When existing rows
violate it, Odoo only logs a warning and runs without the constraint, which is
easy to miss. Failing here aborts the whole upgrade (nothing is written) and
lists the logs to fix first.
"""

import logging

from odoo.tools import SQL
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

LOG_TABLES = ("hpp_log", "metal_log", "weight_log", "x_ray_log", "coding_log")


def _duplicates(cr, table: str) -> list[tuple]:
    cr.execute(
        SQL(
            """
            SELECT production_id, array_agg(id ORDER BY id)
              FROM %s
             WHERE production_id IS NOT NULL
          GROUP BY production_id
            HAVING count(*) > 1
            """,
            SQL.identifier(table),
        )
    )
    return cr.fetchall()


def migrate(cr, version):
    problems = [
        f"{table}: production {production_id} has logs {log_ids}"
        for table in LOG_TABLES
        if table_exists(cr, table)
        for production_id, log_ids in _duplicates(cr, table)
    ]
    if problems:
        raise RuntimeError(
            "impress_quality_logs: cannot add one-log-per-production constraint, "
            "fix these duplicates first:\n" + "\n".join(problems)
        )
    _logger.info("No duplicate logs per production; constraint can be added.")
