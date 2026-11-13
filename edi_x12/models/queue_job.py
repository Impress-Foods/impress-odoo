from odoo import models

FAILED = "failed"
SEND_METHOD = "x12_send_job"
RECEIVE_PROCESS_METHOD = "x12_receive_process_job"


class QueueJob(models.Model):
    _inherit = "queue.job"

    def write(self, vals: dict) -> bool:
        """Extends queue.job.write.

        A send or receive job that ran out of retries leaves its record where it
        was: nothing says so on the record or on the document that caused it. Say
        it there, so someone looks at the failed job and queues the file again.
        """
        result = super().write(vals)
        if vals.get("state") != FAILED:
            return result
        for job in self.filtered(
            lambda j: j.model_name == "edi.exchange.record"
            and j.method_name in (SEND_METHOD, RECEIVE_PROCESS_METHOD)
        ):
            record = job.records.sudo().exists()
            if not record:
                continue
            reason = job.exc_message or job.exc_name or ""
            message = self.env._(
                "The job %(job)s failed and gave up: %(reason)s",
                job=job.name,
                reason=reason,
            )
            record.write({"exchange_error": message})
            record.message_post(body=message)
            record._notify_related_record(message, "error")
        return result
