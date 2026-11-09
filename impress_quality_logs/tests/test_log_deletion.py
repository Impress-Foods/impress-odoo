"""A log that still has lines cannot be deleted; a log without lines can."""

from odoo.exceptions import UserError
from odoo.tests import common, new_test_user

# log model -> (line model, line field pointing to the log)
LOGS_WITH_LINES: dict[str, tuple[str, str]] = {
    "hpp.log": ("hpp.log.line", "hpp_log_id"),
    "metal.log": ("metal.log.line", "metal_log_id"),
    "weight.log": ("weight.log.line", "weight_log_id"),
    "x_ray.log": ("x_ray.log.line", "x_ray_log_id"),
}


class TestLogDeletion(common.TransactionCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.quality_manager = new_test_user(
            cls.env,
            login="log_deletion_manager",
            groups="quality.group_quality_manager",
        )

    def _log_with_line(self, log_model: str):
        line_model, log_field = LOGS_WITH_LINES[log_model]
        log = self.env[log_model].create({"name": f"{log_model} with line"})
        line = self.env[line_model].create({log_field: log.id})
        return log, line

    def test_log_with_lines_cannot_be_deleted(self):
        for log_model in LOGS_WITH_LINES:
            with self.subTest(log=log_model):
                log, line = self._log_with_line(log_model)

                with self.assertRaises(UserError):
                    log.unlink()

                self.assertTrue(log.exists())
                self.assertEqual(log.log_line_ids, line)

    def test_log_without_lines_can_be_deleted(self):
        for log_model in LOGS_WITH_LINES:
            with self.subTest(log=log_model):
                log = self.env[log_model].create({"name": "empty"})
                log.unlink()
                self.assertFalse(log.exists())

    def test_log_can_be_deleted_once_its_lines_are_gone(self):
        for log_model in LOGS_WITH_LINES:
            with self.subTest(log=log_model):
                log, line = self._log_with_line(log_model)
                line.unlink()
                log.unlink()
                self.assertFalse(log.exists())

    def test_coding_log_can_be_deleted(self):
        """Coding logs have no lines, so they are never protected."""
        log = self.env["coding.log"].create({"name": "coding"})
        log.unlink()
        self.assertFalse(log.exists())

    def test_mixed_selection_deletes_nothing(self):
        log_with_line, _line = self._log_with_line("metal.log")
        empty_log = self.env["metal.log"].create({"name": "empty"})

        with self.assertRaises(UserError):
            (log_with_line | empty_log).unlink()

        self.assertTrue(log_with_line.exists())
        self.assertTrue(empty_log.exists())

    def test_quality_manager_is_also_blocked(self):
        """Managers have delete rights on logs; the rule still applies to them."""
        log, _line = self._log_with_line("weight.log")
        empty_log = self.env["weight.log"].create({"name": "empty"})

        with self.assertRaises(UserError):
            log.with_user(self.quality_manager).unlink()
        empty_log.with_user(self.quality_manager).unlink()

        self.assertTrue(log.exists())
        self.assertFalse(empty_log.exists())
