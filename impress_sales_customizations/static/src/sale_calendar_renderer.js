/** @odoo-module **/

import {ActionSwiper} from "@web/core/action_swiper/action_swiper";
import {CalendarRenderer} from "@web/views/calendar/calendar_renderer";

import {SaleCalendarCommonRenderer} from "./sale_calendar_common_renderer";
import {SaleCalendarYearRenderer} from "./sale_calendar_year_renderer";

export class SaleCalendarRenderer extends CalendarRenderer {}

SaleCalendarRenderer.components = {
    day: SaleCalendarCommonRenderer,
    week: SaleCalendarCommonRenderer,
    month: SaleCalendarCommonRenderer,
    year: SaleCalendarYearRenderer,
    ActionSwiper,
};
SaleCalendarRenderer.template = "web.CalendarRenderer";
