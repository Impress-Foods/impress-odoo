/** @odoo-module **/

export async function toggleSoftArchive(model, resModel, resIds, doArchive) {
    const action = await model.orm.call(
        resModel,
        doArchive ? "action_soft_archive" : "action_soft_unarchive",
        [resIds]
    );
    if (action && Object.keys(action).length !== 0) {
        model.action.doAction(action);
    }
    await model.load();
    await model.notify();
    if (doArchive) {
        await model.env.documentsView.bus.trigger("documents-close-preview");
    }
}
