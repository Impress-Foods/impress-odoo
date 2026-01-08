Specification: Odoo 17 Campaign-Based Production Scheduling

1. System Objective

Transition the manufacturing workflow from Discrete MTO (immediate, fragmented MO
creation) to a Process-Style Aggregation Reservoir. The system must intercept demand,
group it by a "Bulk Juice Anchor," and allow for consolidated, batched execution. 2.
Model Schema 2.1 mrp.campaign (The Master Header)

    name: Char (Sequence-based, e.g., CMP/2026/001).

    anchor_product_id: Many2one (product.product). This is the common Bulk Juice.

    date_planned_start: Datetime. The "Single Point of Truth" for scheduling.

    state: Selection (draft, confirmed, done, cancel).

    line_ids: One2many (mrp.campaign.line).

    mo_ids: One2many (mrp.production). Linked production orders.

2.2 mrp.campaign.line (The Demand Reservoir)

    product_id: Many2one (product.product). The SKU being ordered.

    product_uom_qty: Float. Aggregated demand quantity.

    move_dest_ids: Many2many (stock.move). Links back to the original Sales Order/Delivery moves for traceability.

3. Core Logic Requirements 3.1 Demand Interception

Override: mrp.production.run_manufacture() or the Procurement Group's run method. Logic:

    Check if product_id.is_campaign_manufactured is True.

    If True, Recursive Anchor Search:

        Crawl the BOM tree downward.

        Identify the first component where product_id.is_campaign_anchor is True.

    Search/Create Campaign: Find a draft campaign for that Anchor within the target week.

    Update Reservoir: Add the quantity and move_dest_ids to the mrp.campaign.line.

    Suppress Native MO: Return True without creating a standard mrp.production record.

3.2 The Confirmation "Explosion"

Method: action_confirm() on mrp.campaign. Logic:

    SKU Consolidation: Iterate through line_ids. Create one mrp.production per unique product_id.

        Traceability Fix: Manually map line.move_dest_ids to the new MO's move_finished_ids.move_dest_ids.

    WIP Batching:

        Sum total mass of all Finished Goods.

        Generate N Manufacturing Orders for the Anchor Product where N=⌈Total Mass/1000⌉.

        Set sequence on WIP MOs so they are completed linearly.

    Scheduling: Set date_planned_start for all generated MOs to match the mrp.campaign date.

3.3 Synchronized Scheduling

Trigger: Onchange or Write on mrp.campaign.date_planned_start. Logic:

    Update the date_planned_start of all records in mo_ids.

    Maintain the internal sequence (Tanks first, then Bottling).

4. Constraint Handling

   Tank Capacity: The WIP splitting logic must strictly adhere to the 1000kg limit per
   MO.

   No Overnight Bulk: All MOs in a campaign share the same date_planned_start. The AI
   must ensure the "End Date" of the last Tank MO does not exceed the work center's
   daily capacity limit.

5. User Interface

   Kanban View: Group mrp.campaign by date_planned_start:day.

   Drag-and-Drop: Moving a card between columns updates the date of all linked MOs.

   Coloring: Apply color to the mrp.production list view based on the linked
   campaign_id.

6. Technical Implementation Note for Agent

   Important: When creating consolidated MOs, you must preserve the link to the
   stock.move.dest (Delivery Orders). Do not allow the stock.move to be orphaned, or the
   shipping team will lose the ability to reserve stock against specific Sales Orders.
