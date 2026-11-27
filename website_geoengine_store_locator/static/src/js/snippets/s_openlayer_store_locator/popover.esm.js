/**
 * Copyright 2011-2024 Camptocamp SA
 * License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
 */

/* global ol*/

import {escape} from "@web/core/utils/strings";

class Popover {
    constructor(element, map) {
        /**
         * The popover
         * @param {jQuery} popover
         */
        this.popover = undefined;
        /**
         * The map
         * @param {ol.Map} map
         */
        this.map = map;
        /**
         * The base element
         * @param {HTMLElement} element
         */
        this.element = element;
        /**
         * The jQuery base element
         * @type {jQuery}
         */
        this.jqueryElement = $(element);
        /**
         * The popup overlay
         * @param {ol.Overlay} popup
         */
        this.popup = new ol.Overlay({
            element: this.element,
            positioning: "bottom-center",
            stopEvent: false,
        });
        map.addOverlay(this.popup);
        map.on("click", this.mapOnClick.bind(this));
        map.on("pointermove", this.mapOnPointerMove.bind(this));
        map.getView().on("change:center", this.mapOnMove.bind(this));
    }

    /**
     * Dispose the popover
     */
    disposePopover() {
        if (this.popover) {
            this.popover.popover("dispose");
            this.popover = undefined;
        }
    }

    mapOnMove() {
        if (!this.feature) {
            return;
        }
        $(this.element).popover("show");
    }

    /**
     * The function called on map click event
     * @param {ol.MapBrowserEvent} event
     */
    mapOnClick(event) {
        this.feature = this.map.forEachFeatureAtPixel(event.pixel, function (feature) {
            return feature;
        });

        this.disposePopover();
        if (!this.feature) {
            return;
        }
        this.popup.setPosition(this.feature.getGeometry().getFirstCoordinate());
        if (!this.popover) {
            this.popover = $(this.element).popover({
                placement: "top",
                html: true,
                trigger: "focus",
                content: this.buildContent(this.feature),
            });
        }
        this.popover.popover("show");
    }

    /**
     * Build the escaped HTML content of the popover, skipping empty lines
     * @param {ol.Feature} feature
     * @returns {String}
     */
    buildContent(feature) {
        const tags = feature.get("tags");
        const lines = [
            feature.get("street"),
            feature.get("street2"),
            [feature.get("zip"), feature.get("city")].filter(Boolean).join(" "),
            Array.isArray(tags) ? tags.join(", ") : tags,
            feature.get("opening_hours"),
        ].filter(Boolean);
        return [`<b>${escape(feature.get("name"))}</b>`, ...lines.map(escape)].join(
            "<br/>"
        );
    }

    /**
     * The function called on map pointer move event
     * @param {ol.MapBrowserEvent} e
     */
    mapOnPointerMove(e) {
        const pixel = this.map.getEventPixel(e.originalEvent);
        const hit = this.map.hasFeatureAtPixel(pixel);
        this.map.getTarget().style.cursor = hit ? "pointer" : "";
    }
}

export default Popover;
