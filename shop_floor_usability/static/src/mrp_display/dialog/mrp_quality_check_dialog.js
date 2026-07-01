import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {HtmlField} from "@html_editor/fields/html_field";
import {onWillDestroy} from "@odoo/owl";

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
    };

    setup() {
        super.setup();
        this._result = null;
        onWillDestroy(() => {
            this.props.onComplete?.(this._result);
        });
    }

    get check() {
        return this.props.record.data;
    }

    get isPassfail() {
        return this.check.test_type === "passfail";
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
        const action = this.isPassfail ? "action_pass_and_next" : "action_next";
        await this._action(action);
    }

    async pass() {
        await this._action("action_pass_and_next");
    }

    async fail() {
        await this._action("action_fail_and_next");
    }

    skip() {
        this.props.close();
    }

    back() {
        this.props.close();
    }

    async _action(action) {
        return this.execButton(async () => {
            const {model, resModel, resId} = this.props.record;
            this._result = await model.orm.call(resModel, action, [resId], {
                context: {from_shopfloor: true},
            });
        });
    }
}
