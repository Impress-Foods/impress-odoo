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
        const smData = structuredClone(this.cache.getRecord("stock.move", id));
        smData.product_id = this.cache.getRecord("product.product", smData.product_id);
        smData.product_uom_id = this.cache.getRecord("uom.uom", smData.product_uom);
        smData.location_id = this.cache.getRecord("stock.location", smData.location_id);
        smData.location_dest_id = this.cache.getRecord(
            "stock.location",
            smData.location_dest_id
        );
        return smData;
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
                } catch (e) {
                    // Kit info not available in cache
                }
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
                } catch (e) {
                    /* ignore */
                }
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

    totalSupply(product_id) {
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

    // Compute reservation data for a line
    _getReservationData(line) {
        // Handle unreserved lines (no move line, but have stock.move)
        if (line.isUnreservedLine && line._move) {
            const planned = line._move.product_uom_qty || 0;
            return {
                planned: planned,
                reserved: 0,
                done: 0,
                available: planned,
                status: "unreserved",
            };
        }

        const move_id = line.move_id;
        if (!move_id) {
            return {
                planned: 0,
                reserved: 0,
                done: 0,
                available: 0,
                status: "unreserved",
            };
        }

        try {
            const move = this.cache.getRecord("stock.move", move_id);
            const planned = move.product_uom_qty || 0;
            const done = line.qty_done || 0;
            // Reserved = what's reserved in move lines (reserved_uom_qty)
            const reserved = line.reserved_uom_qty || 0;
            // Available = what's physically available but not reserved
            const available = Math.max(0, planned - reserved);

            let status = "complete";
            if (reserved === 0 && planned > 0) {
                status = "unreserved";
            } else if (reserved > 0 && done < planned) {
                status = "partial";
            } else if (done > reserved) {
                status = "over";
            }

            return {planned, reserved, done, available, status};
        } catch (e) {
            return {
                planned: 0,
                reserved: 0,
                done: line.qty_done || 0,
                available: 0,
                status: "unreserved",
            };
        }
    },

    get groupedLines() {
        const res = super.groupedLines;
        res.sort((a, b) => {
            // Get description from line or from move
            let nameA = a.description_picking;
            if (!nameA && a.move_id) {
                try {
                    const moveA = this.cache.getRecord("stock.move", a.move_id);
                    nameA = moveA?.description_picking;
                } catch (e) {
                    /* ignore */
                }
            }
            let nameB = b.description_picking;
            if (!nameB && b.move_id) {
                try {
                    const moveB = this.cache.getRecord("stock.move", b.move_id);
                    nameB = moveB?.description_picking;
                } catch (e) {
                    /* ignore */
                }
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

        const groupColorMap = {};
        let colorIndex = 0;
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

        data.forEach((item) => {
            let groupKey = item.description_picking;

            if (!groupKey && item.move_id) {
                try {
                    const move = this.cache.getRecord("stock.move", item.move_id);
                    groupKey = move?.description_picking;
                } catch (e) {
                    // Ignore errors
                }
            }

            if (groupKey) {
                const sep = groupKey.indexOf(" - ");
                const key =
                    sep !== -1 ? groupKey.slice(0, sep).trim() : groupKey.trim();
                if (groupColorMap[key]) {
                    item.color = groupColorMap[key];
                } else {
                    let newColor;

                    if (colorIndex < maxColors) {
                        newColor = colorPalette[colorIndex];
                    } else {
                        newColor = colorPalette[colorIndex % maxColors];
                    }

                    item.color = newColor;
                    groupColorMap[key] = newColor;
                    colorIndex++;
                }
            } else {
                item.color = "";
            }
        });
    },

    groupKey(line) {
        if (line.isUnreservedLine) {
            return `unreserved_${line.virtual_id}`;
        }
        return super.groupKey(...arguments) + `_${line.location_dest_id.id}`;
    },

    lineCanBeSelected(line) {
        // Unreserved lines cannot be selected (they are display-only)
        if (line.isUnreservedLine) {
            return false;
        }
        return super.lineCanBeSelected(...arguments);
    },
});
