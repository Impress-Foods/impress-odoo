import subprocess
from pathlib import Path

if __name__ == "__main__":
    p = Path(".")
    subdirs = [p / x for x in p.iterdir() if x.is_dir()]
    addons = [subdir for subdir in subdirs if (subdir / "__manifest__.py").exists()]
    addons_with_pot_file = [
        addon for addon in addons if (addon / "i18n" / f"{addon.name}.pot").exists()
    ]

    for addon in addons_with_pot_file:
        if not (addon / "i18n" / "fr_CA.po").exists():
            subprocess.run(
                [
                    "msginit",
                    "-i",
                    f"{addon}/i18n/{addon}.pot",
                    "-o",
                    f"{addon}/i18n/fr_CA.po",
                    "-l",
                    "fr_CA",
                    "--no-translator",
                ]
            )
