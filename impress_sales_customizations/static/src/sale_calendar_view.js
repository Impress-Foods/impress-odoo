/** @odoo-module **/

import {registry} from "@web/core/registry";
import {calendarView} from "@web/views/calendar/calendar_view";
import {SaleCalendarRenderer} from "@impress_sales_customizations/sale_calendar_renderer";

export const SaleCalendarView = {
    ...calendarView,
    Renderer: SaleCalendarRenderer,
};

registry.category("views").add("sale_calendar_view", SaleCalendarView);
