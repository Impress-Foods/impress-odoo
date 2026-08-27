{
    "name": "Impress Customizations",
    "version": "19.0.1.1.1",
    "depends": ["base", "web"],
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "summary": """ Company-wide customizations for Impress Foods""",
    "license": "GPL-2",
    "data": [
        "reports/external_layout.xml",
        "data/external_layout.xml",
        "data/paperformat_data.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "impress/static/src/scss/layout_impress.scss",
        ],
    },
}
