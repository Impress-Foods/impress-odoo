from typing import Any

from odoo.tools.safe_eval import safe_eval


def get_action_context(action: dict[str, Any]) -> dict[str, Any]:
    """Return an action's context as a dict.

    A stored action may carry its context as a dict or as a string, and the
    caller usually wants to add keys to it, so normalise before handing it
    over.
    """
    context = action.get("context") or {}
    if isinstance(context, str):
        context = safe_eval(context)
    return dict(context) if isinstance(context, dict) else {}
