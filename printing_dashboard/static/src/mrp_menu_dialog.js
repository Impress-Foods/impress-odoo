import {MrpMenuDialog} from "@mrp_workorder/mrp_display/dialog/mrp_menu_dialog";
import {patch} from "@web/core/utils/patch";

patch(MrpMenuDialog.prototype, {
    async openPrintDashboard() {
        const action = await this.orm.call(
            this.props.record.resModel,
            "action_open_print_dashboard",
            [[this.props.record.resId]]
        );
        await this.action.doAction(action, {
            onClose: async () => {
                await this.props.reload(this.props.record);
            },
        });
        this.props.close();
    },
});
