{
    "name": "impress_sales_customizations",
    "version": "17.0.0.1.0",
    "depends": ["base", "sale_management", "sale_stock"],
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Sales",
    "summary": """"
    Customizations for the sales module
    """,
    "license": "GPL-2",
    "data": ["views/sale_order_views.xml"],
    "assets": {
        "web.assets_backend": [
            "impress_sales_customizations/static/src/**/*.js",
            "impress_sales_customizations/static/src/**/*.xml",
        ],
    },
}
