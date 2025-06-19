{
    "name": "impress_manufacturing_customizations",
    "version": "17.0.0.1.1",
    "depends": ["base", "mrp"],
    "author": "Cédric Paradis",
    "website": "https://github.com/cparadis-impressfoods/impress-odoo",
    "category": "Manufacturing",
    "summary": """"
    Customizations for the manufacturing module
    """,
    "license": "GPL-2",
    # data files always loaded at installation
    "data": [
        "views/impress_mrp_customizations_production_order_views.xml",
        "views/workorder_dashboard.xml",
    ],
    # data files containing optionally loaded demonstration data
    "demo": [],
}
