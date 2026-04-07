/** @odoo-module **/

import {CalendarYearRenderer} from "@web/views/calendar/calendar_year/calendar_year_renderer";
import {CalendarYearPopover} from "@web/views/calendar/calendar_year/calendar_year_popover";

export class SaleCalendarYearRenderer extends CalendarYearRenderer {
    getPopoverProps(date, records) {
        const res = super.getPopoverProps(date, records);
        for (const record of res.records) {
            if (record.rawRecord && record.rawRecord.client_order_ref) {
                record.title = record.title + " - " + record.rawRecord.client_order_ref;
            }
        }
        return res;
    }
}

SaleCalendarYearRenderer.components = {
    Popover: CalendarYearPopover,
};

SaleCalendarYearRenderer.template = "web.CalendarYearRenderer";
