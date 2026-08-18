import {patch} from "@web/core/utils/patch";
import {DateTimePicker} from "@web/core/datetime/datetime_picker";
import {Time} from "@web/core/l10n/time";

const {DateTime, _Info} = luxon;

patch(DateTimePicker.prototype, {
    getTimeValues(props) {
        const currentTime = DateTime.local();
        const timeValues = this.values.map(
            (val, index) =>
                new Time({
                    hour:
                        index === 1 && !this.values[1]
                            ? (val || currentTime).hour + 1
                            : (val || currentTime).hour,
                    minute: (val || currentTime).minute || 0,
                    second: (val || currentTime).second || 0,
                })
        );

        if (props.range) {
            return timeValues;
        } else {
            const values = [];
            values[props.focusedDateIndex] = timeValues[props.focusedDateIndex];
            return values;
        }
    },
});
