/** @odoo-module **/
import {registry} from "@web/core/registry";
import {CampaignOrchestrator} from "./campaign_orchestrator/campaign_orchestrator";

export const CampaignWidgetField = {
    component: CampaignOrchestrator,
    supportTypes: ["char"],
};

registry.category("fields").add("campaign_orchestrator", CampaignWidgetField);
