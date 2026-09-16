/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";

patch(BarcodePickingModel.prototype, {
    get origin() {
        return this.record.origin;
    },

    _getMoveData(id) {
        const smData = this.cache.getRecord("stock.move", id);
        smData.product_id = this.cache.getRecord("product.product", smData.product_id);
        smData.product_uom_id = this.cache.getRecord("uom.uom", smData.product_uom);
        smData.location_id = this.cache.getRecord("stock.location", smData.location_id);
        smData.location_dest_id = this.cache.getRecord(
            "stock.location",
            smData.location_dest_id
        );
        return smData;
    },

    _getMoveLineData() {
        const smlData = super._getMoveLineData(...arguments);
        // The base implementation assumes any move line unknown from the
        // current state was created in the Barcode App, so its `quantity`
        // holds the done quantity. This is wrong for lines created server-side
        // (e.g. after changing a lot/serial from the line form): such a line is
        // reserved but not picked, so `quantity` is the reservation and the
        // done quantity must stay 0. Without this, the whole reservation is
        // displayed as done with a null demand until a full page reload.
        if (
            smlData.picked === false &&
            smlData.quantity &&
            smlData.qty_done === smlData.quantity
        ) {
            smlData.qty_done = 0;
            smlData.reserved_uom_qty = smlData.quantity;
        }
        return smlData;
    },

    _isSublocation(childLocation, parentLocation) {
        if (!childLocation?.parent_path || !parentLocation?.parent_path) {
            return false;
        }
        return childLocation.parent_path.indexOf(parentLocation.parent_path) === 0;
    },

    // Get unreserved moves formatted as line-compatible objects for LineComponent
    get unreservedLines() {
        // Get raw move data from cache directly
        const moveIds = this.moveIds;
        const lines = this.pageLines;

        // Filter out moves that have lines
        const reservedMoveIds = new Set();
        for (const line of lines) {
            if (line.move_id) {
                reservedMoveIds.add(line.move_id);
            }
        }

        const unreservedMoveIds = moveIds.filter((id) => !reservedMoveIds.has(id));

        // Get full move records directly from cache
        const moves = unreservedMoveIds
            .map((id) => this._getMoveData(id))
            .filter((move) => move.product_uom_qty > 0);
        // Group moves by kit (bom_id) for position calculation
        const kitGroups = {};
        moves.forEach((move, index) => {
            if (move.bom_line_id) {
                try {
                    const bomLine = this.cache.getRecord(
                        "mrp.bom.line",
                        move.bom_line_id
                    );
                    if (bomLine && bomLine.bom_id) {
                        const bom = this.cache.getRecord("mrp.bom", bomLine.bom_id);
                        if (bom && bom.type === "phantom") {
                            const kitKey = bomLine.bom_id;
                            if (!kitGroups[kitKey]) {
                                kitGroups[kitKey] = {bom, moves: []};
                            }
                            kitGroups[kitKey].moves.push({move, index});
                        }
                    }
                } catch {}
            }
        });

        return moves.map((move, index) => {
            // Get description_picking from move data (computed by mrp module)
            let description_picking = move.description_picking || "";

            // If no description_picking but has bom_line_id, try to compute from cache
            if (!description_picking && move.bom_line_id) {
                try {
                    const bomLine = this.cache.getRecord(
                        "mrp.bom.line",
                        move.bom_line_id
                    );
                    if (bomLine && bomLine.bom_id) {
                        const bom = this.cache.getRecord("mrp.bom", bomLine.bom_id);
                        if (bom && bom.type === "phantom") {
                            const kitGroup = kitGroups[bomLine.bom_id];
                            if (kitGroup) {
                                const position =
                                    kitGroup.moves.findIndex((m) => m.index === index) +
                                    1;
                                const total = kitGroup.moves.length;
                                const kitName =
                                    kitGroup.bom.product_id?.display_name || "";
                                description_picking = `${kitName} - ${position}/${total}`;
                            }
                        }
                    }
                } catch {}
            }

            return {
                virtual_id: `unreserved_${move.id}`,
                move_id: move.id,
                product_id: move.product_id,
                reserved_uom_qty: 0,
                qty_done: 0,
                location_id: move.location_id,
                location_dest_id: move.location_dest_id,
                product_uom_id:
                    move.product_uom_id || (move.product_id && move.product_id.uom_id),
                isUnreservedLine: true,
                is_kits: move.product_id && move.product_id.is_kits,
                lot_name: null,
                lot_id: null,
                location_processed: false,
                description_picking: description_picking,
                _move: move,
            };
        });
    },

    // Total demand of a line, summed over every move of its group so grouped
    // lines (kits, multiple lots, ...) report the whole demand instead of a
    // single subline's move.
    _getPlannedQty(line) {
        const sublines = line.lines && line.lines.length ? line.lines : [line];
        const moveIds = [
            ...new Set(sublines.map((subline) => subline.move_id).filter(Boolean)),
        ];
        let planned = 0;
        for (const moveId of moveIds) {
            try {
                const move = this.cache.getRecord("stock.move", moveId);
                planned += move.product_uom_qty || 0;
            } catch {
                // The move isn't (yet) in the cache, ignore it for the demand.
            }
        }
        return planned;
    },

    get groupedLines() {
        const res = [...super.groupedLines];
        res.sort((a, b) => {
            // Get description from line or from move
            let nameA = a.description_picking;
            if (!nameA && a.move_id) {
                try {
                    const moveA = this.cache.getRecord("stock.move", a.move_id);
                    nameA = moveA?.description_picking;
                } catch {}
            }
            let nameB = b.description_picking;
            if (!nameB && b.move_id) {
                try {
                    const moveB = this.cache.getRecord("stock.move", b.move_id);
                    nameB = moveB?.description_picking;
                } catch {}
            }
            nameA = nameA ? nameA.toUpperCase() : "zzz";
            nameB = nameB ? nameB.toUpperCase() : "zzz";
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
            return data;
        }

        const colorPalette = [
            "#7db31a",
            "#4d86a5",
            "#cf0bf1",
            "#3e517a",
            "#fc9f5b",
            "#8c8fe0",
            "#84a75f",
            "#00c7a9",
            "#d60b2d",
            "#1298f1",
        ];
        const maxColors = colorPalette.length;

        const groupKeyOf = (item) => {
            let groupKey = item.description_picking;
            if (!groupKey && item.move_id) {
                try {
                    const move = this.cache.getRecord("stock.move", item.move_id);
                    groupKey = move?.description_picking;
                } catch {}
            }
            if (!groupKey) {
                return "";
            }
            const sep = groupKey.indexOf(" - ");
            return (sep !== -1 ? groupKey.slice(0, sep) : groupKey).trim();
        };

        // Assign the palette on the sorted set of group keys so a group always
        // keeps the same color, whatever the order the lines are rendered in.
        const keys = data.map((item) => groupKeyOf(item));
        const groupColorMap = {};
        const uniqueKeys = [...new Set(keys.filter(Boolean))].sort();
        uniqueKeys.forEach((key, index) => {
            groupColorMap[key] = colorPalette[index % maxColors];
        });

        data.forEach((item, index) => {
            item.color = keys[index] ? groupColorMap[keys[index]] : "";
        });
        return data;
    },

    groupKey(line) {
        if (line.isUnreservedLine) {
            return `unreserved_${line.virtual_id}`;
        }
        return super.groupKey(...arguments) + `_${line.location_dest_id.id}`;
    },

    // Transfer the still-unfulfilled reservation of a sibling line to a newly
    // created line so picking a different lot reassigns the demand instead of
    // leaving the whole reservation stuck on the original lot. Without this,
    // picking 1 unit of lot X (reserved 2) then 1 unit of lot Y shows lot X as
    // "1/2" and lot Y as "1 (0/2)" instead of both as "1/1".
    _stealSiblingReservation(line) {
        if (
            !line ||
            !["lot", "serial"].includes(line.product_id?.tracking) ||
            !line.qty_done ||
            line.reserved_uom_qty ||
            // Package lines count as complete without a reservation and
            // unreserved lines are display-only: never reassign to them.
            line.package_id ||
            line.result_package_id ||
            line.isUnreservedLine
        ) {
            return;
        }
        const donor = this.currentState.lines.find((other) => {
            if (other === line || !other.reserved_uom_qty) {
                return false;
            }
            if (other.qty_done >= other.reserved_uom_qty) {
                return false;
            }
            if (line.move_id && other.move_id) {
                return other.move_id === line.move_id;
            }
            return (
                other.product_id.id === line.product_id.id &&
                other.location_id.id === line.location_id.id &&
                other.location_dest_id.id === line.location_dest_id.id
            );
        });
        if (!donor) {
            return;
        }
        const stolen = Math.min(donor.reserved_uom_qty - donor.qty_done, line.qty_done);
        if (stolen > 0) {
            donor.reserved_uom_qty -= stolen;
            line.reserved_uom_qty = stolen;
        }
    },

    async _createNewLine(params) {
        const newLine = await super._createNewLine(...arguments);
        // Copies/splits (`copyOf`) handle their own reservation, so only
        // reassign the reservation for lines created from a fresh scan.
        if (!params?.copyOf) {
            this._stealSiblingReservation(newLine);
        }
        return newLine;
    },

    lineCanBeSelected(line) {
        // Unreserved lines cannot be selected (they are display-only)
        if (line.isUnreservedLine) {
            return false;
        }
        return super.lineCanBeSelected(...arguments);
    },
});
