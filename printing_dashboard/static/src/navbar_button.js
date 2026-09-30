import {Component} from "@odoo/owl";

import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

/**
 * Global navbar entry point to the printing dashboard.
 *
 * Prefills from the record currently on screen when that model is a dashboard
 * source, so tapping it on a product, lot or transfer opens straight to a
 * sensible set of defaults.  Anything else falls back to a blank dashboard.
 */
export class PrintingDashboardNavbarButton extends Component {
    static template = "printing_dashboard.NavbarButton";
    static props = [];

    setup() {
        super.setup();
        this.action = useService("action");
        this.orm = useService("orm");
    }

    async onClick() {
        const controller = this.action.currentController;
        const resModel = controller?.props?.resModel;
        const resId = controller?.props?.resId;
        let action = false;
        if (resModel) {
            action = await this.orm.call(
                "printing.dashboard",
                "action_open_for_record",
                [resModel, resId || false]
            );
        }
        if (!action) {
            action = "printing_dashboard.action_printing_dashboard";
        }
        await this.action.doAction(action);
    }
}

registry.category("systray").add("printing_dashboard.navbar_button", {
    Component: PrintingDashboardNavbarButton,
});
