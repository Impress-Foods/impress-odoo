/** @odoo-module **/

import {CalendarCommonRenderer} from "@web/views/calendar/calendar_common/calendar_common_renderer";
import {CalendarCommonPopover} from "@web/views/calendar/calendar_common/calendar_common_popover";

export class SaleCalendarCommonRenderer extends CalendarCommonRenderer {}

SaleCalendarCommonRenderer.components = {
    Popover: CalendarCommonPopover,
};

SaleCalendarCommonRenderer.template = "web.CalendarCommonRenderer";
SaleCalendarCommonRenderer.eventTemplate =
    "impress_sales_customizations.SaleCalendarCommonRenderer.event";
SaleCalendarCommonRenderer.headerTemplate = "web.CalendarCommonRendererHeader";
