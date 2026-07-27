import {patch} from "@web/core/utils/patch";
import {MrpDisplayAction} from "@mrp_workorder/mrp_display/mrp_display_action";

patch(MrpDisplayAction.prototype, {
    get fieldsStructure() {
        const res = super.fieldsStructure;
        res["quality.check"].push("can_be_na");
        console.log(res);
        return res;
    },
});
