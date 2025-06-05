{
    "name": "Impress-purchase-customizations",
    "version": "18.0.1.0.0",
    "summary": """ Impress Foods specific purchase customizations """,
    "author": "Cédric Paradis",
    "website": "https://github.com/impress-foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "purchase"],
    "data": [
        "report/purchase_order_report_inherit.xml",
        "report/purchase_order_report.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "GPL-2",
}
