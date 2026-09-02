{
    "name": "ERP Connector - Stock",
    "summary": "Stock module for ERP Connector",
    "version": "19.0.0.1.0",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["connector_erp", "stock"],
    "auto_install": ["connector_erp", "stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/erp_backend_views.xml",
        "views/erp_product_views.xml",
    ],
    "license": "LGPL-3",
}
