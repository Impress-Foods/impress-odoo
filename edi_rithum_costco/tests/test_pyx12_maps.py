"""Tests for the pyx12 maps that ship with the module."""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import pyx12

try:
    from odoo.tests.common import BaseCase as TestCaseBase
except ImportError:  # pragma: no cover - standalone run
    TestCaseBase = unittest.TestCase

if "test_tags" not in vars(TestCaseBase):
    TestCaseBase.test_tags = {"standard", "at_install"}

MODULE_DIR = Path(__file__).resolve().parents[1]
MAP_DIR = MODULE_DIR / "x12_maps"
TSET_MAPS = tuple(
    sorted(
        path.name
        for path in MAP_DIR.glob("*.xml")
        if not path.name.startswith("x12.control")
        and path.name not in ("maps.xml", "dataele.xml", "codes.xml")
    )
)
CONTROL_MAPS = ("x12.control.00401.xml",)

PYX12_DIR = Path(pyx12.__file__).resolve().parent

try:
    from lxml import etree as lxml_etree
except ImportError:  # pragma: no cover - lxml ships with Odoo, but stay safe
    lxml_etree = None


class TestMapContent(TestCaseBase):
    """Structure and policy checks on the committed maps."""

    def test_tset_maps_carry_no_valid_codes_but_hl03(self):
        # Envelope codes live in the control maps; HL03 is the one exception.
        # The 856 is the only map written by us, so it also pins the codes of
        # the elements it fills in, which Rithum rejects the file for.
        for name in TSET_MAPS:
            if name.startswith(("846", "856")):
                continue
            root = ET.parse(MAP_DIR / name).getroot()
            for element in root.iter("element"):
                if element.find("valid_codes") is None:
                    continue
                self.assertEqual(element.get("xid"), "HL03", name)

    def test_the_856_map_pins_the_codes_costco_requires(self):
        root = ET.parse(MAP_DIR / "856.004010.xml").getroot()
        codes = {
            element.get("xid"): [c.text for c in element.iter("code")]
            for element in root.iter("element")
            if element.find("valid_codes") is not None
        }
        self.assertEqual(codes["BSN05"], ["0002"])
        self.assertEqual(codes["SN108"], ["AC", "ID"])
        self.assertEqual(codes["DTM04"][0], "UT")
        self.assertEqual(codes["MAN01"], ["CP"])

    def test_control_map_carries_the_costco_codes(self):
        expected = {"x12.control.00401.xml": ("004010", "PO")}
        for name, (version, functional) in expected.items():
            root = ET.parse(MAP_DIR / name).getroot()
            codes = {
                element.get("xid"): [c.text for c in element.iter("code")]
                for element in root.iter("element")
            }
            self.assertIn(version, codes["GS08"], name)
            self.assertIn(functional, codes["GS01"], name)

    def test_every_map_is_listed_in_the_index(self):
        listed = {m.text for m in ET.parse(MAP_DIR / "maps.xml").getroot().iter("map")}
        self.assertEqual(listed, set(TSET_MAPS))


@unittest.skipIf(lxml_etree is None, "needs lxml")
class TestMapsAgainstPyx12(TestCaseBase):
    """pyx12's own schema and loader accept the maps."""

    def test_maps_validate_against_pyx12_schema(self):
        schema = lxml_etree.XMLSchema(
            lxml_etree.parse(str(PYX12_DIR / "map" / "map.xsd"))
        )
        for name in TSET_MAPS + CONTROL_MAPS:
            document = lxml_etree.parse(str(MAP_DIR / name))
            self.assertTrue(schema.validate(document), f"{name}: {schema.error_log}")

    def test_maps_load_with_pyx12_loader(self):
        from pyx12.map_if._loader import load_map_file
        from pyx12.params import params

        options = params()
        for name in TSET_MAPS:
            load_map_file(name, options, map_path=str(MAP_DIR))


if __name__ == "__main__":
    unittest.main()
