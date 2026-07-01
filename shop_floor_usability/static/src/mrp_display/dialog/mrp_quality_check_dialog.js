import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {HtmlField} from "@html_editor/fields/html_field";
import {FloatField} from "@web/views/fields/float/float_field";
import {Field} from "@web/views/fields/field";
import {onWillDestroy} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

export class QualityCheckDialog extends ConfirmationDialog {
    static template = "shop_floor_usability.QualityCheckDialog";
    static props = {
        ...ConfirmationDialog.props,
        record: Object,
        onComplete: {type: Function, optional: true},
    };
    static components = {
        ...ConfirmationDialog.components,
        HtmlField,
        FloatField,
        Field,
    };

    setup() {
        super.setup();
        this._result = null;
        this._stateToSet = null;
        this.action = useService("action");
        onWillDestroy(() => {
            this.props.onComplete?.(this._result, this._stateToSet);
        });
    }

    get check() {
        return this.props.record.data;
    }

    get isPassfail() {
        return this.check.test_type === "passfail";
    }

    get isMeasure() {
        return this.check.test_type === "measure";
    }

    get htmlInfo() {
        return {
            name: "note",
            record: this.props.record,
            readonly: true,
            embeddedComponents: true,
        };
    }

    async validate() {
        if (this.isMeasure) {
            return this._actionMeasure();
        }
        if (this.isPassfail) {
            return this._action("action_pass_and_next", "pass");
        }
        return this._action("action_next", "pass");
    }

    async pass() {
        await this._action("action_pass_and_next", "pass");
    }

    async fail() {
        await this._action("action_fail_and_next", "fail");
    }

    skip() {
        this.props.close();
    }

    back() {
        this.props.close();
    }

    async _action(action, stateToSet = "pass") {
        return this.execButton(async () => {
            const {model, resModel, resId} = this.props.record;
            this._result = await model.orm.call(resModel, action, [resId], {
                context: {from_shopfloor: true},
            });
            this._stateToSet = stateToSet;
        });
    }

    async _actionMeasure() {
        return this.execButton(async () => {
            await this.props.record.save({reload: false});
            const {model, resModel, resId} = this.props.record;
            this._result = await model.orm.call(resModel, "do_measure", [resId], {
                context: {from_shopfloor: true},
            });
            this._stateToSet = "pass";
        });
    }
}
