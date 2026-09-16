import {expect, test} from "@odoo/hoot";
import {
    defineModels,
    makeMockEnv,
    mountWithCleanup,
} from "@web/../tests/web_test_helpers";
import {mailModels} from "@mail/../tests/mail_test_helpers";
import {Component, xml} from "@odoo/owl";
import {user} from "@web/core/user";

import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";

defineModels(mailModels);

const NOMENCLATURE = {id: 1, rule_ids: []};

function makeRecords() {
    return {
        "barcode.nomenclature": [NOMENCLATURE],
        "stock.picking": [
            {
                id: 1,
                name: "PICK/0001",
                origin: "SO0001",
                state: "assigned",
                move_ids: [100, 101],
                move_line_ids: [10],
                location_id: 1,
                location_dest_id: 2,
            },
        ],
        "stock.move": [
            {
                id: 100,
                product_id: 1,
                location_id: 1,
                location_dest_id: 2,
                product_uom_qty: 10,
                product_uom: 1,
                move_line_ids: [10],
            },
            {
                id: 101,
                product_id: 1,
                location_id: 1,
                location_dest_id: 2,
                product_uom_qty: 10,
                product_uom: 1,
                move_line_ids: [],
            },
        ],
        "stock.move.line": [
            {
                id: 10,
                move_id: 100,
                product_id: 1,
                product_uom_id: 1,
                location_id: 1,
                location_dest_id: 2,
                quantity: 10,
                qty_done: 0,
                picked: false,
                lot_id: false,
                lot_name: false,
                package_id: false,
                result_package_id: false,
                outermost_result_package_id: false,
                owner_id: false,
                is_entire_pack: false,
                dummy_id: false,
                description_picking: "Product A",
            },
        ],
        "product.product": [
            {
                id: 1,
                display_name: "Product A",
                uom_id: 1,
                tracking: "lot",
                is_kits: false,
            },
        ],
        "uom.uom": [{id: 1, name: "Unit", factor: 1}],
        "stock.location": [
            {id: 1, display_name: "WH/Stock", name: "Stock", usage: "internal"},
            {id: 2, display_name: "Partner", name: "Partner", usage: "customer"},
        ],
        "stock.picking.type": [],
        "res.partner": [],
        "stock.package": [],
        "stock.package.type": [],
        "stock.lot": [{id: 5, name: "LOT-Y", product_id: 1}],
        "product.uom": [],
        "mrp.bom": [],
        "mrp.bom.line": [],
    };
}

function makeBarcodeData(records) {
    return {
        actionId: 1,
        data: {
            records: records || makeRecords(),
            nomenclature_id: 1,
            config: {},
        },
        groups: {},
    };
}

class ModelHost extends Component {
    static template = xml`<div/>`;
    static props = {};
    setup() {
        this.model = new BarcodePickingModel("stock.picking", 1, this.env.services);
    }
}

async function makeModel(env) {
    if (!env) {
        env = await makeMockEnv();
    }
    const host = await mountWithCleanup(ModelHost, {env});
    return host.model;
}

test("a recreated move line keeps its reservation", async () => {
    const model = await makeModel();
    model.setData(makeBarcodeData());

    let line = model.pageLines.find((l) => l.id === 10);
    expect(line.reserved_uom_qty).toBe(10);
    expect(line.qty_done).toBe(0);

    // Simulate a lot/serial change from the line form: the move line is
    // recreated server-side with a new id, still reserved but not picked.
    const records = makeRecords();
    records["stock.picking"][0].move_line_ids = [11];
    records["stock.move.line"] = [{...records["stock.move.line"][0], id: 11}];
    model.cache.setCache(records);
    model._createState();

    line = model.pageLines.find((l) => l.id === 11);
    expect(line.reserved_uom_qty).toBe(10);
    expect(line.qty_done).toBe(0);
});

test("planned qty sums the demand of every move of a grouped line", async () => {
    const model = await makeModel();
    model.setData(makeBarcodeData());

    const groupedLine = {
        lines: [{move_id: 100}, {move_id: 101}],
        reserved_uom_qty: 20,
        qty_done: 0,
    };
    expect(model._getPlannedQty(groupedLine)).toBe(20);
});

test("picking a new lot reassigns the remaining reservation", async () => {
    const model = await makeModel();
    model.setData(makeBarcodeData());

    // 1 unit of lot X was picked on the initially reserved line (2 reserved).
    const lotXLine = model.pageLines.find((l) => l.id === 10);
    lotXLine.reserved_uom_qty = 2;
    lotXLine.qty_done = 1;
    model.selectedLineVirtualId = lotXLine.virtual_id;
    // Avoid `_setUser` firing a `stock.picking` write RPC the mock server doesn't know.
    model.record.user_id = user.userId;

    // Scanning 1 unit of lot Y creates a new line on the same move.
    await model._createNewLine({
        fieldsParams: {
            product_id: lotXLine.product_id,
            lot_id: model.cache.getRecord("stock.lot", 5),
            qty_done: 1,
        },
    });

    const lotYLine = model.currentState.lines.find(
        (l) => l.lot_id && l.lot_id.id === 5
    );
    expect(lotYLine).not.toBe(undefined);
    expect(lotXLine.reserved_uom_qty).toBe(1);
    expect(lotYLine.reserved_uom_qty).toBe(1);
});

test("reassigned reservation survives a full page reload", async () => {
    const env = await makeMockEnv();

    // Session 1: pick 1 unit of lot X, then 1 unit of lot Y on a 2-unit move.
    const model = await makeModel(env);
    model.setData(makeBarcodeData());
    const lotXLine = model.pageLines.find((l) => l.id === 10);
    lotXLine.reserved_uom_qty = 2;
    lotXLine.qty_done = 1;
    model.selectedLineVirtualId = lotXLine.virtual_id;
    model.record.user_id = user.userId;
    await model._createNewLine({
        fieldsParams: {
            product_id: lotXLine.product_id,
            lot_id: model.cache.getRecord("stock.lot", 5),
            qty_done: 1,
        },
    });
    expect(lotXLine.reserved_uom_qty).toBe(1);

    // Full reload: the server now stores one picked move line per lot, so the
    // model must derive each line's reservation from its `quantity`.
    const baseLine = makeRecords()["stock.move.line"][0];
    const records = makeRecords();
    records["stock.picking"][0].move_line_ids = [10, 11];
    records["stock.move"][0].move_line_ids = [10, 11];
    records["stock.move.line"] = [
        {...baseLine, lot_name: "LOT-X", quantity: 1, qty_done: 1, picked: true},
        {...baseLine, id: 11, lot_id: 5, quantity: 1, qty_done: 1, picked: true},
    ];

    const reloaded = await makeModel(env);
    reloaded.setData(makeBarcodeData(records));

    const reloadedLotX = reloaded.pageLines.find((l) => l.id === 10);
    const reloadedLotY = reloaded.pageLines.find((l) => l.id === 11);
    expect(reloadedLotX.reserved_uom_qty).toBe(1);
    expect(reloadedLotY.reserved_uom_qty).toBe(1);
    expect(reloadedLotX.qty_done).toBe(1);
    expect(reloadedLotY.qty_done).toBe(1);
});

test("planned qty is reported for an unreserved move", async () => {
    const model = await makeModel();
    model.setData(makeBarcodeData());

    const line = model.unreservedLines.find((l) => l.move_id === 101);
    expect(line).not.toBe(undefined);
    expect(model._getPlannedQty(line)).toBe(10);
});

test("a split (copied) line does not steal the sibling reservation", async () => {
    const model = await makeModel();
    model.setData(makeBarcodeData());

    // 1 unit of lot X picked, 1 still reserved on the same line.
    const lotXLine = model.pageLines.find((l) => l.id === 10);
    lotXLine.reserved_uom_qty = 2;
    lotXLine.qty_done = 1;
    model.selectedLineVirtualId = lotXLine.virtual_id;
    model.record.user_id = user.userId;

    // Splitting copies the line and manages the reservation itself, so the
    // source line must keep its full remaining reservation.
    await model._createNewLine({
        copyOf: lotXLine,
        fieldsParams: {product_id: lotXLine.product_id, qty_done: 1},
    });
    expect(lotXLine.reserved_uom_qty).toBe(2);
});

test("no reservation is reassigned to a package line", async () => {
    const model = await makeModel();
    model.setData(makeBarcodeData());

    const donor = model.pageLines.find((l) => l.id === 10);
    donor.reserved_uom_qty = 2;
    donor.qty_done = 1;

    const packageLine = {
        move_id: donor.move_id,
        product_id: donor.product_id,
        location_id: donor.location_id,
        location_dest_id: donor.location_dest_id,
        reserved_uom_qty: 0,
        qty_done: 1,
        package_id: {id: 99},
        result_package_id: {id: 99},
    };
    model._stealSiblingReservation(packageLine);
    expect(packageLine.reserved_uom_qty).toBe(0);
    expect(donor.reserved_uom_qty).toBe(2);
});
