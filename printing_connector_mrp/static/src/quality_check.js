import {patch} from "@web/core/utils/patch";
import {QualityCheck} from "@mrp_workorder/mrp_display/mrp_record_line/quality_check";
import {PrintDialog} from "./mrp_print_dialog";

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
            const data = await new Promise((resolve) => {
                this.dialog.add(PrintDialog, {
                    record: this.props.record,
                    confirm: (data) => resolve(data),
                    cancel: () => resolve(null),
                    confirmLabel: "Print",
                });
            });

            if (!data) {
                return;
            }

            this.extraContext = {
                printing_printing_quantity: data.qty,
                printing_printer_override: data.printer_id,
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
});
