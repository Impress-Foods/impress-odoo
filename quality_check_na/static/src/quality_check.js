import {patch} from "@web/core/utils/patch";
import {QualityCheck} from "@mrp_workorder/mrp_display/mrp_record_line/quality_check";

patch(QualityCheck.prototype, {
    naCheck() {
        this.state.reOpened = false;
        return this.doActionAndNext("action_na_and_next", "na");
    },

    get skipped() {
        return this.check.quality_state === "na";
    },

    get isComplete() {
        return super.isComplete || this.skipped;
    },
    get showQty() {
        if (this.passFailTypes.includes(this.type) && this.isComplete) {
            return this.passed ? "passed" : this.skipped ? "N/A" : "failed";
        }
        return super.showQty;
    },
    get canBeNa() {
        return this.props.record.data.can_be_na;
    },
});
