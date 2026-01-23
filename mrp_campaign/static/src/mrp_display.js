/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {MrpDisplay} from "@mrp_workorder/mrp_display/mrp_display";

patch(MrpDisplay.prototype, {
    get relevantRecords() {
        const records = super.relevantRecords;
        if (!records || records.length === 0) {
            return records;
        }

        const productionDates = {};

        for (const prod of this.productions) {
            productionDates[prod.data.id] = prod.data.date_start;
        }

        const statesComparativeValues = {
            progress: 0,
            ready: 1,
            pending: 2,
            waiting: 3,
            finished: 4,
        };

        // --- 1. Pre-calculate the earliest date per Campaign Group ---
        const groupMinDates = {};

        for (const record of records) {
            const campaignId = record.data.campaign_id ? record.data.campaign_id[0] : 0;

            const prodId =
                this.state.activeResModel == "mrp.workorder"
                    ? record.data.production_id[0]
                    : record.data.id;

            // Use .ts if Odoo has already parsed these as Luxon objects, otherwise new Date()
            const dateVal = productionDates[prodId]
                ? productionDates[prodId]
                : Infinity;
            if (!(campaignId in groupMinDates) || dateVal < groupMinDates[campaignId]) {
                groupMinDates[campaignId] = dateVal;
            }
        }

        // --- 2. Perform the Hierarchical Sort ---
        records.sort((record1, record2) => {
            const cid1 = record1.data.campaign_id ? record1.data.campaign_id[0] : 0;
            const cid2 = record2.data.campaign_id ? record2.data.campaign_id[0] : 0;

            // Level A: Sort Groups by their earliest Start Date
            if (cid1 !== cid2) {
                return groupMinDates[cid1] - groupMinDates[cid2];
            }

            // Level B: Within the same group, sort by Campaign Sequence (descending)
            const seq1 = record1.data.campaign_sequence ?? 0;
            const seq2 = record2.data.campaign_sequence ?? 0;
            if (seq1 !== seq2) {
                return seq2 - seq1; // Descending order
            }

            // Level C: Within the same group, sort by State Priority
            const v1 = statesComparativeValues[record1.data.state] ?? 99;
            const v2 = statesComparativeValues[record2.data.state] ?? 99;
            if (v1 !== v2) {
                return v1 - v2;
            }

            // Level D: Within the same state, sort by individual Start Date
            const d1 = record1.data.date_start
                ? new Date(record1.data.date_start).getTime()
                : 0;
            const d2 = record2.data.date_start
                ? new Date(record2.data.date_start).getTime()
                : 0;
            return d1 - d2;
        });
        return records;
    },
});
