from typing import Any

from odoo.tests.common import TransactionCase

from odoo.addons.mrp.models.mrp_bom import MrpBom
from odoo.addons.product.models.product_product import ProductProduct
from odoo.addons.product.models.product_template import ProductTemplate

from ..models.mrp_campaign import MrpCampaign
from ..models.mrp_campaign_demand import MrpCampaignDemand
from ..models.mrp_campaign_line import CampaignLine


class CampaignCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids |= cls.env.ref("base.group_user")
        cls.env.user.group_ids |= cls.env.ref("base.group_partner_manager")
        cls.env.user.group_ids |= cls.env.ref("mrp.group_mrp_manager")
        cls.env.user.group_ids |= cls.env.ref("stock.group_stock_manager")

        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.company = cls.env.ref("base.main_company")

        product_template_model: ProductTemplate = cls.env["product.template"]
        product_model: ProductProduct = cls.env["product.product"]
        mrp_bom_model: MrpBom = cls.env["mrp.bom"]
        product_attribute_model = cls.env["product.attribute"]
        product_attribute_value_model = cls.env["product.attribute.value"]
        uom_unit = cls.env.ref("uom.product_uom_unit")

        # --- Product Attributes and Values ---
        cls.color_attribute = product_attribute_model.create(
            {"name": "Color", "sequence": 1}
        )
        cls.color_red = product_attribute_value_model.create(
            {
                "name": "Red",
                "attribute_id": cls.color_attribute.id,
                "sequence": 1,
            }
        )
        cls.color_blue = product_attribute_value_model.create(
            {
                "name": "Blue",
                "attribute_id": cls.color_attribute.id,
                "sequence": 2,
            }
        )
        cls.color_green = product_attribute_value_model.create(
            {
                "name": "Green",
                "attribute_id": cls.color_attribute.id,
                "sequence": 3,
            }
        )

        # --- Bulk Materials ---
        cls.bulk_material = product_model.create(
            {
                "name": "Bulk Material M",
                "type": "consu",
                "is_storable": True,
                "uom_id": uom_unit.id,
                "mrp_max_batch_size": 1000.0,
                "campaign_buffer_percent": 0.05,
            }
        )
        cls.bulk_material.product_tmpl_id.is_campaign_anchor = True

        cls.bom_bulk_material = mrp_bom_model.create(
            {
                "product_tmpl_id": cls.bulk_material.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
            }
        )

        # --- Intermediate Products (with Variants) ---
        cls.int_prod_x_tmpl = product_template_model.create(
            {
                "name": "Intermediate Product X",
                "type": "consu",
                "is_storable": True,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": cls.color_attribute.id,
                            "value_ids": [
                                (6, 0, [cls.color_red.id, cls.color_blue.id])
                            ],
                        },
                    )
                ],
            }
        )
        cls.int_prod_x_red = cls.int_prod_x_tmpl.product_variant_ids.filtered(
            lambda p: (
                cls.color_red
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )
        cls.int_prod_x_blue = cls.int_prod_x_tmpl.product_variant_ids.filtered(
            lambda p: (
                cls.color_blue
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )

        cls.int_prod_y_tmpl = product_template_model.create(
            {
                "name": "Intermediate Product Y",
                "type": "consu",
                "is_storable": True,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": cls.color_attribute.id,
                            "value_ids": [
                                (6, 0, [cls.color_red.id, cls.color_blue.id])
                            ],
                        },
                    )
                ],
            }
        )
        cls.int_prod_y_red = cls.int_prod_y_tmpl.product_variant_ids.filtered(
            lambda p: (
                cls.color_red
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )
        cls.int_prod_y_blue = cls.int_prod_y_tmpl.product_variant_ids.filtered(
            lambda p: (
                cls.color_blue
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )

        # --- End Products (Campaign Anchors with Variants) ---
        cls.end_prod_a_tmpl = product_template_model.create(
            {
                "name": "End Product A",
                "type": "consu",
                "is_storable": True,
                "is_campaign_anchor": False,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": cls.color_attribute.id,
                            "value_ids": [
                                (6, 0, [cls.color_red.id, cls.color_blue.id])
                            ],
                        },
                    ),
                ],
            }
        )
        cls.end_prod_a_red = cls.end_prod_a_tmpl.product_variant_ids.filtered(
            lambda p: (
                cls.color_red
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )
        cls.end_prod_a_blue = cls.end_prod_a_tmpl.product_variant_ids.filtered(
            lambda p: (
                cls.color_blue
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )

        cls.end_prod_b_tmpl = product_template_model.create(
            {
                "name": "End Product B",
                "type": "consu",
                "is_storable": True,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": cls.color_attribute.id,
                            "value_ids": [
                                (6, 0, [cls.color_red.id, cls.color_blue.id])
                            ],
                        },
                    )
                ],
            }
        )
        cls.end_prod_b_red = cls.end_prod_b_tmpl.product_variant_ids.filtered(
            lambda p: (
                cls.color_red
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )
        cls.end_prod_b_blue = cls.end_prod_b_tmpl.product_variant_ids.filtered(
            lambda p: (
                cls.color_blue
                in p.product_template_variant_value_ids.product_attribute_value_id
            )
        )

        # --- BOMs ---
        # BOM for Intermediate Product X
        cls.bom_int_prod_x = mrp_bom_model.create(
            {
                "product_tmpl_id": cls.int_prod_x_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.bulk_material.id,
                            "product_qty": 3.0,
                        },
                    ),
                ],
            }
        )

        # BOM for Intermediate Product Y
        cls.bom_int_prod_y = mrp_bom_model.create(
            {
                "product_tmpl_id": cls.int_prod_y_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.bulk_material.id,
                            "product_qty": 3.0,
                        },
                    )
                ],
            }
        )

        cls.ptav_int_prod_x_red = (
            cls.int_prod_x_tmpl.attribute_line_ids.product_template_value_ids.filtered(
                lambda ptav: ptav.product_attribute_value_id == cls.color_red
            )
        )
        cls.ptav_int_prod_x_blue = (
            cls.int_prod_x_tmpl.attribute_line_ids.product_template_value_ids.filtered(
                lambda ptav: ptav.product_attribute_value_id == cls.color_blue
            )
        )
        cls.ptav_int_prod_y_red = (
            cls.int_prod_y_tmpl.attribute_line_ids.product_template_value_ids.filtered(
                lambda ptav: ptav.product_attribute_value_id == cls.color_red
            )
        )
        cls.ptav_int_prod_y_blue = (
            cls.int_prod_y_tmpl.attribute_line_ids.product_template_value_ids.filtered(
                lambda ptav: ptav.product_attribute_value_id == cls.color_blue
            )
        )

        cls.ptav_end_prod_a_red = (
            cls.end_prod_a_tmpl.attribute_line_ids.product_template_value_ids.filtered(
                lambda ptav: ptav.product_attribute_value_id == cls.color_red
            )
        )
        cls.ptav_end_prod_a_blue = (
            cls.end_prod_a_tmpl.attribute_line_ids.product_template_value_ids.filtered(
                lambda ptav: ptav.product_attribute_value_id == cls.color_blue
            )
        )
        cls.ptav_end_prod_b_red = (
            cls.end_prod_b_tmpl.attribute_line_ids.product_template_value_ids.filtered(
                lambda ptav: ptav.product_attribute_value_id == cls.color_red
            )
        )
        cls.ptav_end_prod_b_blue = (
            cls.end_prod_b_tmpl.attribute_line_ids.product_template_value_ids.filtered(
                lambda ptav: ptav.product_attribute_value_id == cls.color_blue
            )
        )

        # BOM for End Product A
        cls.bom_end_prod_a = mrp_bom_model.create(
            {
                "product_tmpl_id": cls.end_prod_a_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.int_prod_x_red.id,
                            "product_qty": 2.0,
                            "bom_product_template_attribute_value_ids": [
                                cls.ptav_end_prod_a_red.id
                            ],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": cls.int_prod_x_blue.id,
                            "product_qty": 2.0,
                            "bom_product_template_attribute_value_ids": [
                                cls.ptav_end_prod_a_blue.id
                            ],
                        },
                    ),
                ],
            }
        )

        # BOM for End Product B
        cls.bom_end_prod_b = mrp_bom_model.create(
            {
                "product_tmpl_id": cls.end_prod_b_tmpl.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.int_prod_y_red.id,
                            "product_qty": 2.0,
                            "bom_product_template_attribute_value_ids": [
                                cls.ptav_end_prod_b_red.id
                            ],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": cls.int_prod_y_blue.id,
                            "product_qty": 2.0,
                            "bom_product_template_attribute_value_ids": [
                                cls.ptav_end_prod_b_blue.id
                            ],
                        },
                    ),
                ],
            }
        )

        # --- Product without BOM ---
        cls.product_no_bom = product_model.create(
            {
                "name": "Product Without BOM",
                "type": "consu",
                "is_storable": True,
                "uom_id": uom_unit.id,
            }
        )

    @classmethod
    def create_campaign(
        cls, product: ProductProduct, workflow_type: str = "direct"
    ) -> MrpCampaign:
        return cls.env["mrp.campaign"].create(
            {"product_id": product.id, "workflow_type": workflow_type}
        )

    @classmethod
    def create_line(
        cls, product: ProductProduct, campaign: MrpCampaign | None = None
    ) -> CampaignLine:
        values = {}
        values["product_id"] = product.id
        bom = cls.env["mrp.bom"]._bom_find(product).get(product)
        values["bom_id"] = bom.id if bom else False
        values["campaign_id"] = campaign.id if campaign else False
        return cls.env["mrp.campaign.line"].create(values)

    @classmethod
    def create_demand(
        cls,
        product: ProductProduct,
        qty: float = 1.0,
        campaign: MrpCampaign | None = None,
    ) -> MrpCampaignDemand:
        demand = cls.env["mrp.campaign.demand"].create(
            {
                "product_id": product.id,
                "campaign_id": campaign.id if campaign else False,
            }
        )

        move = cls.env["stock.move"].create(
            {
                "product_id": product.id,
                "product_uom_qty": qty,
                "location_id": cls.stock_location.id,
                "location_dest_id": cls.stock_location.id,
                "state": "waiting",
            }
        )

        cls.env["mrp.campaign.demand.target"].create(
            {
                "demand_id": demand.id,
                "promised_qty": qty,
                "target_id": move.id,
            }
        )

        return demand

    @classmethod
    def get_all_values_for_key(
        cls, target: dict, target_key: Any, result=None
    ) -> list[Any]:
        if result is None:
            result = []

        for key, value in target.items():
            if key == target_key:
                result.append(value)
            elif isinstance(value, dict):
                cls.get_all_values_for_key(value, target_key, result)
            elif isinstance(value, list):
                for item in value:
                    cls.get_all_values_for_key(item, target_key, result)

        return result


class CampaignDirectCase(CampaignCase):
    @classmethod
    def create_full_campaign(cls, product, qty):
        """Creates campaign, demand, move, and target for testing."""
        campaign = cls.create_campaign(cls.bulk_material)
        campaign.workflow_type = "direct"
        demand = cls.create_demand(product, qty, campaign)
        target = demand.target_ids[0]
        move = target._get_target()
        return campaign, demand, move, target

    @classmethod
    def create_target(cls, demand, move, promised_qty):
        """Creates a single target."""
        return cls.env["mrp.campaign.demand.target"].create(
            {
                "demand_id": demand.id,
                "workflow_type": "direct",
                "promised_qty": promised_qty,
            }
        )
