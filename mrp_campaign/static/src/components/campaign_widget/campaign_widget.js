/** @odoo-module **/
import {registry} from "@web/core/registry";
import {CampaignOrchestrator} from "./campaign_orchestrator/campaign_orchestrator";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

export const CampaignWidgetField = {
    component: CampaignOrchestrator,
    supportTypes: ["char"],
};

// Registering it so you can use widget="campaign_orchestrator" in XML
registry.category("fields").add("campaign_orchestrator", CampaignWidgetField);
