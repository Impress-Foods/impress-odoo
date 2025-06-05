{
    "name": "Impress Stock Customizations",
    "version": "18.0.0.1.1",
    "depends": ["base", "stock"],
    "author": "Cédric Paradis",
    "website": "https://github.com/impress-foods/impress-odoo",
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
    ],
}
