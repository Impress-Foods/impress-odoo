{
    "name": "Impress Stock Customizations",
    "version": "19.0.1.1.3",
    "depends": ["base", "stock", "product_expiry"],
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Inventory",
    "summary": """
    Customizations for the stock module developped in-house by Impress Foods SEC
    """,
    "license": "GPL-2",
    # data files always loaded at installation
    "data": [
        "reports/paperformat_data.xml",
        "reports/impress_stock_customizations_stock_delivery_document_views.xml",
        "reports/impress_stock_customizations_labels.xml",
        "reports/online_sale_labels.xml",
        "reports/stock_picking_document_views.xml",
        "views/stock_lot_views.xml",
        "views/res_partner_views.xml",
        "reports/stock_picking_with_checks_report.xml",
        "reports/report_deliveryslip.xml",
        "views/product_template_views.xml",
        "reports/report_online_sales_summary_report.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "impress_stock_customizations/static/src/**/*.scss"
        ]
    },
}
