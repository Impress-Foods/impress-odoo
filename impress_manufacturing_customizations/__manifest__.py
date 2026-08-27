{
    "name": "Impress Manufacturing Customizations",
    "version": "19.0.1.1.0",
    "depends": ["base", "mrp", "mrp_workorder", "sale_mrp", "impress"],
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Manufacturing",
    "summary": """Customizations for the manufacturing module""",
    "license": "GPL-2",
    "data": [
        "views/mrp_production_views.xml",
        "views/workorder_dashboard.xml",
        "reports/mrp_production_job_sheet.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "impress_manufacturing_customizations/static/src/**/*.scss"
        ]
    },
}
