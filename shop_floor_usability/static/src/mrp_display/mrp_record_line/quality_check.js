import {patch} from "@web/core/utils/patch";
import {QualityCheck} from "@mrp_workorder/mrp_display/mrp_record_line/quality_check";
import {QualityCheckDialog} from "../dialog/mrp_quality_check_dialog";
import {AdditionalNoteDialog} from "../dialog/mrp_additional_note_dialog";

patch(QualityCheck.prototype, {
    setup() {
        super.setup();
        this.props.record.component = this;
    },
    async clicked() {
        if (["instructions", "passfail", "measure"].includes(this.type)) {
            if (this.isComplete && this.type !== "measure") {
                return super.clicked();
            }
            if (this.type === "measure" && this.isComplete) {
                this.props.record.data.quality_state = "none";
            }
            const [result, stateToSet] = await new Promise((resolve) => {
                this.dialog.add(QualityCheckDialog, {
                    record: this.props.record,
                    onComplete: (result, stateToSet) => resolve([result, stateToSet]),
                });
            });
            if (result) {
                if (result.type === "ir.actions.act_window") {
                    const {data} = this.props.record;
                    data.quality_state = "none";
                    await this.action.doAction(result, {
                        onClose: () => this.env.reload(this.props.record),
                    });
                    return;
                }
                if ("next_check_id" in result) {
                    const {_parentRecord} = this.props.record;
                    this.props.record.update({quality_state: stateToSet || "pass"});
                    _parentRecord.update({
                        current_quality_check_id: result.next_check_id,
                    });
                    _parentRecord.model.notify();
                }
                await this._chainToNext(result);
            }
            return;
        }
        return super.clicked();
    },
    async doActionAndNext(action, stateToSet = "pass") {
        const {model, resModel, resId, data, _parentRecord} = this.props.record;
        const result = await model.orm.call(resModel, action, [resId], {
            context: {from_shopfloor: true},
        });
        if ("next_check_id" in result) {
            this.props.record.update({quality_state: stateToSet});
            _parentRecord.update({current_quality_check_id: result.next_check_id});
            _parentRecord.model.notify();
        }
        if ("type" in result) {
            const params = {};
            if (result.type === "ir.actions.act_window") {
                params.onClose = () => this.env.reload(this.props.record);
                data.quality_state = "none";
            }
            await this.action.doAction(result, params);
            return this.props.startWorking();
        }
        if (result?.next_check_id) {
            await this._chainToNext(result);
        }
        return this.props.startWorking();
    },
    async _chainToNext(result) {
        if (!result?.next_check_id) return;
        const _parentRecord = this.props.record._parentRecord;
        const checks = _parentRecord.data.check_ids.records;
        const nextCheck = checks.find((c) => c.resId === result.next_check_id);
        if (nextCheck?.component) {
            await new Promise((r) => setTimeout(r));
            await nextCheck.component.clicked();
        }
    },
    async _onClickAdditionalNote() {
        const {dialog} = this;
        const props = {
            title: "Additional Note",
            record: this.props.record,
        };
        await dialog.add(AdditionalNoteDialog, props);
    },
});
