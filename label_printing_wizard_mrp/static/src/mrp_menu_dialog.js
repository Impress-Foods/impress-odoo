import {patch} from "@web/core/utils/patch";
import {MrpMenuDialog} from "@mrp_workorder/mrp_display/dialog/mrp_menu_dialog";

patch(MrpMenuDialog.prototype, {
    async openLabelWizard() {
        const action = await this.orm.call(
            this.props.record.resModel,
            "action_open_label_wizard",
            [[this.props.record.resId]],
            {
                context: {
                    from_shop_floor: true,
                },
            }
        );
        await this.action.doAction(action, {
            onClose: async () => {
                await this.props.reload(this.props.record);
            },
        });
        this.props.close();
    },
});
