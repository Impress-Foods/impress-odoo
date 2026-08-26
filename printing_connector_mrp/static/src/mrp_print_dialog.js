import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {onWillStart, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

export class PrintDialog extends ConfirmationDialog {
    static template = "printing_connector_mrp.PrintDialog";
    static props = {
        ...ConfirmationDialog.props,
        record: Object,
    };

    setup() {
        super.setup();
        this.orm = useService("orm");

        this.state = useState({
            printers: [],
            printer_id: null,
            qty: 1,
        });

        this.selected = {printer_id: null, qty: null};

        onWillStart(async () => {
            const resId = this.props.record.resId;
            const data = await this.orm.call("quality.check", "get_print_data", [
                resId,
            ]);
            Object.assign(this.state, data);
            this.selected.printer_id = data.printer_id;
            this.selected.qty = data.qty;
        });
    }

    validate() {
        this.selected.printer_id = this.state.printer_id;
        this.selected.qty = this.state.qty;
        this.props.confirm?.(this.selected);
        this.props.close();
    }
}
