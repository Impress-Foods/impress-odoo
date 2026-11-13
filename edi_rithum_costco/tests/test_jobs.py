"""Files of an X12 backend leave and enter through queue jobs, after commit."""

import base64
from unittest import mock

from odoo.tests.common import new_test_user

from odoo.addons.integration_queue_job.exception import RetryableJobError
from odoo.addons.integration_queue_job.tests.common import trap_jobs

from .common import TRACKING, CostcoShipmentCase
from .test_flow_850 import _order_text

SEND = "x12_send_job"
RECEIVE = "x12_receive_process_job"


class TestJobs(CostcoShipmentCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Jobs are really queued here, not run on the spot.
        cls.env = cls.env(context=dict(cls.env.context, queue_job__no_delay=False))

    def _shipment(self, picking=None, kits=3):
        """Validate a delivery; the shipment confirmation record it produces."""
        if picking is None:
            __, picking = self._order(kits=kits)
            self._pack(picking, [kits])
        self._validate(picking, tracking=TRACKING[:1])
        return picking.exchange_record_ids.filtered(
            lambda r: r.type_id.code == "costco_856_out"
        )

    def _jobs(self, method):
        return self.env["queue.job"].search([("method_name", "=", method)])

    def test_the_upload_is_queued_not_done_in_the_transaction(self):
        __, picking = self._order()
        self._pack(picking, [3])
        with trap_jobs() as trap:
            record = self._shipment(picking)
            trap.assert_jobs_count(1, only=record.x12_send_job)
            self.assertEqual(record.edi_exchange_state, "output_pending")
            self.assertTrue(record.exchange_file)
        with (
            trap_jobs() as trap,
            mock.patch.object(
                self.env.registry["edi.backend"], "exchange_send"
            ) as send,
        ):
            record.action_exchange_send()
            send.assert_not_called()
            trap.perform_enqueued_jobs()
            send.assert_called_once()

    def test_a_rollback_leaves_no_job_behind(self):
        __, picking = self._order()
        self._pack(picking, [3])
        before = self._jobs(SEND)
        with self.assertRaises(RuntimeError), self.env.cr.savepoint():
            self._shipment(picking)
            self.assertTrue(self._jobs(SEND) - before)
            raise RuntimeError("the transaction fails after the action")
        self.assertEqual(self._jobs(SEND), before)

    def test_a_second_request_for_the_same_upload_adds_no_job(self):
        record = self._shipment()
        record.action_exchange_send()
        self.assertEqual(
            len(self._jobs(SEND).filtered(lambda j: record in j.records)), 1
        )

    def test_a_failing_upload_is_retried_and_the_record_stays_pending(self):
        record = self._shipment()
        backend = self.env.registry["edi.backend"]
        with mock.patch.object(backend, "_exchange_send", side_effect=OSError("down")):
            with self.assertRaises(RetryableJobError):
                record.x12_send_job()
        self.assertEqual(record.edi_exchange_state, "output_pending")

    def test_an_upload_failure_outside_a_job_is_not_a_retryable_error(self):
        record = self._shipment()
        backend = self.env.registry["edi.backend"]
        with (
            mock.patch.object(backend, "_exchange_send", side_effect=OSError("down")),
            self.assertRaises(OSError),
        ):
            record.with_context(x12_in_job=False).backend_id.exchange_send(record)

    def test_a_job_that_gave_up_says_so_on_the_record_and_the_delivery(self):
        record = self._shipment()
        job = self._jobs(SEND).filtered(lambda j: record in j.records)
        job.write({"state": "failed", "exc_message": "connection refused"})
        self.assertIn("connection refused", record.exchange_error)
        picking = record.record
        self.assertIn(
            "connection refused", " ".join(picking.message_ids.mapped("body"))
        )
        self.assertEqual(record.edi_exchange_state, "output_pending")

    def test_a_generation_error_reaches_the_delivery_at_once(self):
        unspecified = self.carrier.copy({"costco_shipping_method": "UNSP"})
        __, picking = self._order()
        self._pack(picking, [3])
        self._validate(picking, tracking=TRACKING[:1], carrier=unspecified)
        self.assertIn("could not be sent", " ".join(picking.message_ids.mapped("body")))
        self.assertFalse(
            self._jobs(SEND).filtered(lambda j: picking.exchange_record_ids & j.records)
        )

    def test_a_failed_generation_can_be_sent_again_once_fixed(self):
        unspecified = self.carrier.copy({"costco_shipping_method": "UNSP"})
        __, picking = self._order()
        self._pack(picking, [3])
        self._validate(picking, tracking=TRACKING[:1], carrier=unspecified)
        (record,) = picking.exchange_record_ids.filtered(
            lambda r: r.type_id.code == "costco_856_out"
        )
        self.assertFalse(record.exchange_file)
        unspecified.costco_shipping_method = "UPSN_CG"
        record.action_x12_resend()
        self.assertTrue(record.exchange_file)
        self.assertEqual(record.edi_exchange_state, "output_pending")
        self.assertTrue(self._jobs(SEND).filtered(lambda j: record in j.records))

    def test_a_warehouse_user_can_queue_the_upload(self):
        user = new_test_user(self.env, login="x12_wh", groups="stock.group_stock_user")
        __, picking = self._order()
        self._pack(picking, [3])
        picking.write(
            {"carrier_id": self.carrier.id, "carrier_tracking_ref": TRACKING[0]}
        )
        picking.with_user(user).with_context(
            skip_immediate=True, skip_backorder=True
        ).button_validate()
        (record,) = picking.exchange_record_ids.filtered(
            lambda r: r.type_id.code == "costco_856_out"
        )
        self.assertFalse(record.exchange_error, record.exchange_error)
        self.assertTrue(self._jobs(SEND).filtered(lambda j: record in j.records))

    def test_the_confirmation_waits_for_the_backorder_notice(self):
        __, picking = self._order(kits=3)
        self._pack(picking, [2])
        confirmation = self._shipment(picking)
        backorder = self.env["stock.picking"].search(
            [("backorder_id", "=", picking.id)]
        )
        (notice,) = backorder.exchange_record_ids
        self.assertEqual(confirmation._x12_send_blockers(), notice)
        with self.assertRaises(RetryableJobError):
            confirmation.x12_send_job()
        with mock.patch.object(self.env.registry["edi.backend"], "exchange_send"):
            notice.x12_send_job()
        self._jobs(SEND).filtered(lambda j: notice in j.records).write(
            {"state": "done"}
        )
        self.assertFalse(confirmation._x12_send_blockers())

    def test_each_inbound_file_gets_its_own_job(self):
        files = [
            self.backend.create_record("rithum_in", {"exchange_file": self._b64(text)})
            for text in (_order_text(po_number="PO-A"), _order_text(po_number="PO-B"))
        ]
        records = self.env["edi.exchange.record"].union(*files)
        with trap_jobs() as trap:
            for record in records:
                record.action_exchange_receive_process_chained()
            trap.assert_jobs_count(2)

    def test_processing_a_file_twice_acknowledges_it_once(self):
        record = self.backend.create_record(
            "rithum_in",
            {
                "exchange_file": self._b64(_order_text(po_number="PO-ONCE")),
                "edi_exchange_state": "input_received",
            },
        )
        record.x12_receive_process_job()
        record.x12_receive_process_job()
        acks = self.env["edi.exchange.record"].search(
            [("parent_id", "=", record.id), ("type_id.code", "=", "rithum_997_out")]
        )
        self.assertEqual(len(acks), 1)
        self.assertEqual(record.ack_exchange_id, acks)

    def _b64(self, text):
        return base64.b64encode(text.encode("cp1252"))
