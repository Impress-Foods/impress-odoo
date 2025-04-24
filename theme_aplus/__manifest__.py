{
    "name": "Theme A+",
    "version": "17.0.1.0.0",
    "summary": """ A+ Theme """,
    "author": "Cédric Paradis",
    "website": "",
    "category": "Theme/Website",
    "depends": ["web", "website", "web_editor"],
    "data": ["views/snippets/options.xml", "views/snippets/s_wave_transition.xml"],
    "assets": {
        "web._assets_primary_variables": [
            "theme_aplus/static/src/scss/_aplus_colors.scss",
            "theme_aplus/static/src/scss/primary_variables.scss",
        ],
        "web.assets_frontend": [
            "theme_aplus/static/src/snippets/s_wave_transition/000.js",
            "theme_aplus/static/src/snippets/s_wave_transition/000.scss",
            "theme_aplus/static/src/snippets/s_wave_transition/000.xml",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
