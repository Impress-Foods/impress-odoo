import {patch} from "@web/core/utils/patch";
import {QualityCheck} from "@mrp_workorder/mrp_display/mrp_record_line/quality_check";

patch(QualityCheck.prototype, {
    setup() {
        super.setup();
        this.extraContext = {};
    },

    get test_report_type() {
        return this.check.test_report_type;
    },

    async clicked() {
        if (this.type == "print_label" && this.test_report_type == "api") {
            const action = await this.props.record.model.orm.call(
                this.props.record.resModel,
                "action_open_print_wizard",
                [this.props.record.resId]
            );
            const wizardId = action.res_id;

            const selection = await new Promise((resolve) => {
                this.action
                    .doAction(action, {
                        onClose: async () => {
                            const [wizard] = await this.props.record.model.orm.read(
                                "print.wizard",
                                [wizardId],
                                ["result_ready", "result_printer_id", "result_qty"]
                            );
                            resolve(wizard?.result_ready ? wizard : null);
                        },
                    })
                    .catch(() => resolve(null));
            });

            if (!selection) {
                return;
            }

            this.extraContext = {
                printing_printing_quantity: selection.result_qty,
                printing_printer_override: selection.result_printer_id?.[0],
            };
            return this.doActionAndNext("action_print");
        } else {
            return super.clicked();
        }
    },

    async doActionAndNext(action, stateToSet = "pass") {
        if (this.type == "print_label" && this.test_report_type == "api") {
            const {model, resModel, resId, data, _parentRecord} = this.props.record;
            const result = await model.orm.call(resModel, action, [resId], {
                context: {from_shopfloor: true, ...this.extraContext},
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
        } else {
            return super.doActionAndNext(action, stateToSet);
        }
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
});
