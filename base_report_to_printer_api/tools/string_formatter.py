from collections.abc import Callable

# The transformations a mapping's ``formatting`` field may name. The allowlist
# is explicit so a profile cannot reach arbitrary ``str`` methods. A name
# outside it is skipped rather than rejected: a mis-typed option must never
# stop a print job, so the mapping still prints, just without the intended
# transformation.
STRING_TRANSFORMS: dict[str, Callable[[str], str]] = {
    "lower": str.lower,
    "upper": str.upper,
    "title": str.title,
    "capitalize": str.capitalize,
    "strip": str.strip,
    "lstrip": str.lstrip,
    "rstrip": str.rstrip,
}


def format_string(value: str, format_spec: str | None = None) -> str:
    """Normalize a mapped string, applying comma-separated transforms.

    Leading and trailing whitespace is always removed, whether or not
    ``format_spec`` names a ``strip``. Unknown transform names are ignored.
    """
    if not value:
        return ""

    for command in (format_spec or "").split(","):
        transform = STRING_TRANSFORMS.get(command.strip())
        if transform:
            value = transform(value)

    return value.strip()
