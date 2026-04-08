{
    "name": "Impress-purchase-customizations",
    "version": "19.0.1.0.0",
    "summary": """ Impress Foods specific purchase customizations """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "purchase"],
    "data": [
        "report/purchase_order_report.xml",
        "security/groups.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "GPL-2",
}
