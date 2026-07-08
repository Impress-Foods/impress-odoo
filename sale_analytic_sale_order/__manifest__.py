{
    "name": "Sale Analytic Account on Order Header",
    "summary": "Restore analytic_account_id on sale.order (Odoo 17 feature)",
    "version": "19.0.1.0.0",
    "author": "Cédric Paradis",
    "category": "Sales",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "depends": ["sale", "analytic"],
    "data": [
        "views/sale_order_views.xml",
    ],
    "application": False,
    "auto_install": False,
    "license": "GPL-2",
}
