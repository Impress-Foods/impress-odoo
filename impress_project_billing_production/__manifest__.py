{
    "name": "impress_project_production_billing",
    "version": "19.0.1.0.0",
    "summary": """
        Impress Foods customization to allow billing of MOs through projects DEPRECATED
    """,
    "category": "Services",
    "author": "Cédric Paradis",
    "website": "https://github.com/impress-foods/impress-odoo",
    "license": "LGPL-3",
    "depends": [
        "base",
        "base_automation",
        "account",
        "product",
        "analytic",
        "project",
        "mrp",
        "timesheet_grid",
        "account_accountant",
        "sale_management",
    ],
    "data": [
        "views/sale_order_views.xml",
        "views/mrp_production_views.xml",
    ],
}
