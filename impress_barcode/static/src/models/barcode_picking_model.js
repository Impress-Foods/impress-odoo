/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";

patch(BarcodePickingModel.prototype, {
    getTotalDemand(move_id) {
        try {
            return this.cache.getRecord("stock.move", move_id)["product_uom_qty"];
        } catch (error) {
            return 0;
        }
    },

    get origin() {
        return this.record.origin;
    },

    _getMoveData(id) {
        const smData = this.cache.getRecord("stock.move", id);
        smData.product_id = this.cache.getRecord("product.product", smData.product_id);
        return smData;
    },

    get unreservedMoves() {
        const move_ids = this.moveIds;
        const lines = this.pageLines;
        for (const line of lines) {
            const move_id = line.move_id;
            const index = move_ids.indexOf(move_id);
            if (index != -1) {
                move_ids.splice(index, 1);
            }
        }
        const moves = move_ids.map((x) => this._getMoveData(x));
        return moves;
    },

    totalSupply(product_id) {
        // We need to check every stock move line
        // to grab the ones with this product
        const move_lines = this.cache.dbIdCache["stock.move.line"];
        let total = 0;

        for (const key in move_lines) {
            const line = move_lines[key];
            if (line.product_id == product_id) {
                total += line.qty_done;
            }
        }
        return total;
    },

    get groupedLines() {
        const res = super.groupedLines;
        res.sort((a, b) => {
            const nameA = a.description_bom_line
                ? a.description_bom_line.toUpperCase()
                : "zzz";
            const nameB = b.description_bom_line
                ? b.description_bom_line.toUpperCase()
                : "zzz";
            if (nameA < nameB) {
                return -1;
            }
            if (nameA > nameB) {
                return 1;
            }
            return 0;
        });
        this.assignGroupColors(res);
        return res;
    },

    assignGroupColors(data) {
        if (!Array.isArray(data) || data.length === 0) {
            return data; // Return empty/invalid data as is
        }

        // --- Internal State (local to this function call) ---
        const groupColorMap = {};
        let colorIndex = 0;
        const colorPalette = [
            "#E6194B", // Red
            "#309b3eff", // Green
            "#4363D8", // Blue
            "#F58231", // Orange
            "#911EB4", // Purple
            "#46F0F0", // Cyan
            "#F032E6", // Magenta
            "#BFEF45", // Lime
            "#008080", // Teal
            "#9A6324", // Brown
        ];
        const maxColors = colorPalette.length;

        // --- Processing ---
        data.forEach((item) => {
            const groupKey = item.description_bom_line;

            // 1. Check if the item belongs to a valid group
            if (groupKey) {
                // Ensure the key is treated as a string and trimmed
                let key = "";
                if (item.description_bom_line.indexOf(" - ")) {
                    key = String(groupKey)
                        .slice(0, item.description_bom_line.indexOf(" - "))
                        .trim();
                } else {
                    key = String(groupKey).trim();
                }
                // Check if this group has been seen before
                if (groupColorMap[key]) {
                    // Group seen: Assign the existing color
                    item.color = groupColorMap[key];
                } else {
                    // New group: Assign a new color
                    let newColor;

                    if (colorIndex < maxColors) {
                        // Use the next unique color
                        newColor = colorPalette[colorIndex];
                    } else {
                        // Cycle colors if the limit is reached (or use a different fallback)
                        newColor = colorPalette[colorIndex % maxColors];
                        // console.warn(`Color limit reached. Cycling colors for group: ${key}`);
                    }

                    item.color = newColor;
                    groupColorMap[key] = newColor; // Store the assignment
                    colorIndex++; // Move to the next color index
                }
            } else {
                // 2. Item has no valid group key: Assign default color
                item.color = "";
            }
        });
    },
});
