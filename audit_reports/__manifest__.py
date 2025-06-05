{
    "name": "Audit_reports",
    "version": "18.0.0.0.1",
    "summary": """ Audit_reports Summary """,
    "author": "Cédric Paradis",
    "website": "https://github.com/impress-foods/impress-odoo",
    "category": "Hidden",
    "depends": [
        "base",
        "stock",
        "product_expiry",
        "mrp",
        "sale_stock",
        "purchase_stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/wizard_make_traceability_report.xml",
        "views/stock_lot_views.xml",
        "reports/lot_audit_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "audit_reports/static/src/**/*",
            "audit_reports/static/src/scss/audit_report.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "GPL-2",
}
