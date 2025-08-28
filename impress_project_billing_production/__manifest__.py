{
    "name": "impress_project_production_billing",
    "version": "17.0.0.1.0",
    "summary": """
        Impress Foods customization to allow billing of MOs through projects DEPRECATED
    """,
    "category": "Services",
    "author": "Cédric Paradis",
    "website": "https://github.com/Impress-Foods/impress-odoo",
    "license": "LGPL-3",
    # Dependencies
    "depends": [
        "base",
        "base_automation",
        "account",
        "product",
        "analytic",
        "project",
        "mrp",
        "timesheet_grid",
        "account_accountant",
        "sale_management",
    ],
    # Also depends on the follwing custom fields:
    # project.project.x_billing_so
    # production.order.x_related_project
    #
    # It also requires the following records:
    # An employee with name "Impress"
    # An analytic plan with name "Pulp & Press"
    # Data files always loaded
    "data": [
        "actions/server_actions.xml",
        "actions/automation_rules.xml",
        "views/sale_order_views.xml",
        "views/mrp_production_views.xml",
        "portal/portal_views.xml",
    ],
}
