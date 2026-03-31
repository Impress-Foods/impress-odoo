from odoo import api, fields, models


class MrpCampaignDemandTarget(models.Model):
    _name = "mrp.campaign.demand.target"
    _description = "Demand target - maps demand to external source"
    _order = "id"

    demand_id = fields.Many2one(
        "mrp.campaign.demand",
        required=True,
        ondelete="cascade",
    )
    campaign_id = fields.Many2one(related="demand_id.campaign_id")

    workflow_type = fields.Selection(related="campaign_id.workflow_type")

    target_id = fields.Many2oneReference(model_field="target_model")
    target_model = fields.Char(compute="_compute_target_model", store=True)

    promised_qty = fields.Float(required=True, default=0.0)

    upstream_qty = fields.Float(
        string="Upstream Demand",
        compute="_compute_upstream_qty",
    )

    is_fully_planned = fields.Boolean(
        compute="_compute_is_fully_planned",
        store=True,
    )

    def _get_target(self) -> models.Model:
        self.ensure_one()
        model = self.target_model
        return self.env[model].browse(self.mapped("target_id"))

    @api.depends("workflow_type")
    def _compute_target_model(self) -> None:
        for rec in self:
            if rec.workflow_type == "direct":
                rec.target_model = "stock.move"

    @api.depends("promised_qty", "upstream_qty")
    def _compute_is_fully_planned(self) -> None:
        for rec in self:
            rec.is_fully_planned = rec.promised_qty >= rec.upstream_qty

    @api.depends("workflow_type", "target_id")
    def _compute_upstream_qty(self) -> None:
        for rec in self:
            if not rec.target_id or not rec.target_model:
                rec.upstream_qty = 0.0
                continue
            if rec.workflow_type == "direct":
                rec.upstream_qty = rec._get_target().product_uom_qty

    def _get_partition_wizard_fields(self):
        """Return dict of target fields for partition wizard.

        Schema:
            - target_id: int - Target record ID
            - product_id: int - Product ID
            - product_name: str - Product display name
            - promised_qty: float - Current promised quantity
            - fulfilled_qty: float - Quantity already produced/in progress
            - upstream_qty: float - Quantity needed from upstream (needed_qty)
            - is_fully_planned: bool - Whether promised meets upstream

        Workflow-specific fields (added by override):
            - origin: str - Source document reference
            - customer: str - Customer name
            - uom: str - Unit of measure display name
            - deadline: str - Date deadline (YYYY-MM-DD)
            - customer_ref: str - Customer reference from sale order
        """
        self.ensure_one()
        fulfilled_qty = 0.0
        res = {
            "target_id": self.id,
            "product_id": self.demand_id.product_id.id,
            "product_name": self.demand_id.product_id.display_name,
            "promised_qty": 0,  # Intentional, clean slate for widget, will be filled
            "fulfilled_qty": fulfilled_qty,
            "upstream_qty": self.upstream_qty,
            "is_fully_planned": self.is_fully_planned,
            "campaign_line_id": self.demand_id.campaign_line_id.id,
        }
        if self.workflow_type == "direct":
            move = self._get_target()
            res.update(
                {
                    "origin": move.origin or move.picking_id.name
                    if move.picking_id
                    else False,
                    "customer": move.partner_id.name or "Internal",
                    "uom": move.product_uom.display_name,
                    "deadline": move.date_deadline.strftime("%Y-%m-%d")
                    if move.date_deadline
                    else False,
                }
            )
            group_id = move.group_id
            if group_id and group_id.sale_id:
                res["customer_ref"] = group_id.sale_id.client_order_ref
        return res


class MrpCampaignDemand(models.Model):
    _name = "mrp.campaign.demand"
    _description = "Manufacturing Campaign Demand Line"

    campaign_id = fields.Many2one("mrp.campaign", string="Campaign", ondelete="cascade")

    campaign_line_id = fields.Many2one("mrp.campaign.line")
    product_id = fields.Many2one("product.product", string="Product", required=True)
    product_tmpl_id = fields.Many2one(
        "product.template", related="product_id.product_tmpl_id"
    )

    target_qty = fields.Float(
        string="Target Quantity",
        compute="_compute_target_qty",
        store=True,
        help="Quantity to produce for this demand (sum of promised quantities).",
    )

    product_uom_id = fields.Many2one(
        "uom.uom", string="Unit of Measure", related="product_id.uom_id"
    )

    bom_id = fields.Many2one(
        "mrp.bom",
        string="Bill of Materials",
        help="The specific BoM to be used for manufacturing the product on this line.",
    )

    target_ids = fields.One2many(
        "mrp.campaign.demand.target",
        "demand_id",
    )

    @api.depends("target_ids", "target_ids.promised_qty")
    def _compute_target_qty(self):
        for rec in self:
            rec.target_qty = sum(rec.target_ids.mapped("promised_qty"))

    def _get_anchor_factor(self) -> float:
        self.ensure_one()
        return self.campaign_line_id._get_anchor_factor()

    def unlink(self):
        self.target_ids.unlink()
        return super().unlink()

    def create_campaign_line(self):
        created_lines = self.env["mrp.campaign.line"]
        for rec in self:
            bom = rec.bom_id or self.env["mrp.bom"]._bom_find(
                products=rec.product_id, company_id=rec.campaign_id.company_id.id
            ).get(rec.product_id)

            new_line = self.env["mrp.campaign.line"].create(
                {
                    "campaign_id": rec.campaign_id.id,
                    "product_id": rec.product_id.id,
                    "bom_id": bom.id if bom else False,
                }
            )
            created_lines |= new_line
            rec.campaign_line_id = new_line

        return created_lines
