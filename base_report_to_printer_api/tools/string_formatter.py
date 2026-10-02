def format_string(value: str, format_string: str | None = None) -> str:
    """Normalize mapped strings while leaving formatting to Odoo/QWeb."""
    return value.strip()
