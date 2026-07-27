import {patch} from "@web/core/utils/patch";
import {MrpDisplayRecord} from "@mrp_workorder/mrp_display/mrp_display_record";

patch(MrpDisplayRecord.prototype, {
    _workorderDisplayDoneButton() {
        return (
            ["pending", "waiting", "ready", "progress"].includes(this.record.state) &&
            this.record.check_ids.records.every((qc) =>
                ["pass", "fail", "na"].includes(qc.data.quality_state)
            )
        );
    },
});
