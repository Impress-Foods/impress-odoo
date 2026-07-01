import {patch} from "@web/core/utils/patch";
import {MrpDisplayEmployeesPanel} from "@mrp_workorder/mrp_display/employees_panel";
import {useRef, useState} from "@odoo/owl";

patch(MrpDisplayEmployeesPanel.prototype, {
    setup() {
        super.setup();
        this.state = useState({collapsed: false});
        this.rootRef = useRef("root");
    },
    toggleCollapse() {
        this.state.collapsed = !this.state.collapsed;
    },
});
