{
    "name": "impress_project_production_billing",
    "version": "19.0.1.0.0",
    "summary": """
        Impress Foods customization to allow billing of MOs through projects DEPRECATED
    """,
    "category": "Services",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "license": "LGPL-3",
    "depends": [
        "base_automation",
        "mrp",
        "timesheet_grid",
        "account_accountant",
        "sale_management",
        "sale_project",
    ],
    "data": [
        "views/sale_order_views.xml",
        "views/mrp_production_views.xml",
    ],
}
