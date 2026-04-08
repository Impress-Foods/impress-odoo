{
    "name": "Impress Stock Customizations",
    "version": "19.0.1.0.0",
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
        "reports/impress_stock_customizations_stock_delivery_document_views.xml",
        "reports/impress_stock_customizations_labels.xml",
        "reports/online_sale_labels.xml",
        "reports/stock_picking_document_views.xml",
        "reports/report_templates.xml",
        "views/stock_lot_views.xml",
        "views/res_partner_views.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "impress_stock_customizations/static/src/**/*.scss"
        ]
    },
}
