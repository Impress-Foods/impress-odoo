{
    "name": "impress_sales_customizations",
    "version": "19.0.1.2.0",
    "depends": ["base", "sale_management", "sale_stock", "stock_delivery"],
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Sales",
    "summary": """Customizations for the sales module""",
    "license": "GPL-2",
    "data": [
        "views/sale_order_views.xml",
        "report/report_commercial_invoice.xml",
        "views/product_template_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "impress_sales_customizations/static/src/**/*.js",
            "impress_sales_customizations/static/src/**/*.xml",
        ],
        "web.report_assets_common": [
            "impress_sales_customizations/static/src/report.scss"
        ],
    },
}
