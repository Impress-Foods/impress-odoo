{
    "name": "Impress Check Customizations",
    "version": "17.0.0.1.0",
    "summary": """Small tweaks to l10n_ca_check to allow better
    printing on preprinted checks """,
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "category": "Hidden",
    "depends": ["base", "web", "l10n_ca_check_printing"],
    "data": [],
    "assets": {
        "web.report_assets_common": ["impress_check_customizations/static/src/**/*"],
    },
    "installable": True,
    "license": "GPL-2",
}
