{
    "name": "impress_datetime_widget",
    "version": "19.0.0.1.0",
    "depends": ["base", "web"],
    "author": "Cédric Paradis",
    "category": "Technical",
    "summary": """
    Module to restore the default DateTime picker widget behavior from Odoo V15
    where the default time selected
    when a widget is opened is the current time without any rounding.
    """,
    "website": "https://github.com/impress-foods/impress-odoo",
    "license": "GPL-2",
    # data files always loaded at installation
    "assets": {
        "web.assets_backend": ["impress_datetime_widget/static/src/datetime_picker.js"]
    },
}
