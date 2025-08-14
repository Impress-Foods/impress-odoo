{
    "name": "Warehouse Space Billing",
    "version": "17.0.0.0.1",
    "category": "Inventory/Billing",
    "summary": """
        This module allows billing customers based on the warehouse space
        utilized by their products on a daily basis.
        Features:
        - Track daily warehouse space usage per client
        - Configure billing rates
        - Generate monthly invoices automatically
    """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "depends": [
        "base",
        "stock",
        "product",
        "account",
        "uom",
        "sale_management",
    ],
    "data": [
        "data/ir_sequence.xml",
        "data/warehouse_cron.xml",
        "security/warehouse_billing_security.xml",
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/quant_history_views.xml",
        "views/res_partner_views.xml",
        "views/warehouse_billing_config_views.xml",
        "views/warehouse_quant_group_views.xml",
        "wizards/wizard_create_quant_history.xml",
        "views/menus.xml",
        "data/billing_config_actions.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "GPL-2",
}
