/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {DateTimePicker} from "@web/core/datetime/datetime_picker";
import {ensureArray} from "@web/core/utils/arrays";

import {MAX_VALID_DATE, MIN_VALID_DATE, clampDate, today} from "@web/core/l10n/dates";

const {DateTime, Info} = luxon;

const parseLimitDate = (value, defaultValue) =>
    clampDate(
        value === "today" ? today() : value || defaultValue,
        MIN_VALID_DATE,
        MAX_VALID_DATE
    );

patch(DateTimePicker.prototype, {
    onPropsUpdated(props) {
        this.values = ensureArray(props.value).map((value) =>
            value && !value.isValid ? null : value
        );

        this.allowedPrecisionLevels = this.filterPrecisionLevels(
            props.minPrecision,
            props.maxPrecision
        );

        this.maxDate = parseLimitDate(props.maxDate, MAX_VALID_DATE);
        this.minDate = parseLimitDate(props.minDate, MIN_VALID_DATE);
        if (this.props.type === "date") {
            this.maxDate = this.maxDate.endOf("day");
            this.minDate = this.minDate.startOf("day");
        }

        if (this.maxDate < this.minDate) {
            throw new Error(
                `DateTimePicker error: given "maxDate" comes before "minDate".`
            );
        }
        const currentTime = DateTime.local();
        //console.log(currentTime);
        //console.log(this.values);
        const timeValues = this.values.map((val) => [
            (val || currentTime).hour,
            (val || currentTime).minute || 0,
            (val || currentTime).second || 0,
        ]);

        if (props.range) {
            this.state.timeValues = timeValues;
        } else {
            this.state.timeValues = [];
            this.state.timeValues[props.focusedDateIndex] =
                timeValues[props.focusedDateIndex];
        }
        // Debugging: console.log(this.state.timeValues);
        this.shouldAdjustFocusDate = !props.range;
        this.adjustFocus(this.values, props.focusedDateIndex);
        //this.handle12HourSystem();
        this.state.timeValues = this.state.timeValues.map((timeValue) =>
            timeValue.map(String)
        );
    },
});
