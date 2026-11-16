# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YaolinDong
"""Keep PDF corrections reproducible when EDA regenerates attribute IDs."""
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from schematic_svg import CONFIG, prepare_svg


class SvgPresentationTests(unittest.TestCase):
    def test_regenerated_pin_attribute_ids_preserve_the_rendered_text(self):
        with zipfile.ZipFile(ROOT / 'docs/schematics/native-svg-R8.zip') as archive:
            for name in archive.namelist():
                sheet = next(p.stem for p in (ROOT / 'hardware/infrabot_pcb_4p3/sch/Schematic1').glob('*.esch2') if f'-{p.stem}_' in name)
                original = ET.fromstring(archive.read(name))
                reopened = ET.fromstring(archive.read(name))
                for group in reopened.iter():
                    if group.get('c_partid') == 'part_pin':
                        for i, text in enumerate(n for n in group if n.tag.endswith('text')):
                            text.set('id', f'regenerated-{group.get("id")}-{i}')
                self.assertEqual(prepare_svg(original, sheet), prepare_svg(reopened, sheet))
                def displayed_text(root):
                    return [(''.join(t.itertext()), t.get('x'), t.get('y'), t.get('transform')) for t in root.iter() if t.tag.endswith('text')]
                self.assertEqual(displayed_text(original), displayed_text(reopened), sheet)

    def test_changed_pin_identity_rejects_an_outdated_offset(self):
        item = json.loads(CONFIG.read_text())['sheets']['Core_BTB'][0]
        with zipfile.ZipFile(ROOT / 'docs/schematics/native-svg-R8.zip') as archive:
            root = ET.fromstring(archive.read(next(n for n in archive.namelist() if '-Core_BTB_' in n)))
        group = next(e for e in root.iter() if e.get('id') == item['parent_id'])
        text = [e for e in group if e.tag.endswith('text')][item['text_index']]
        text.clear()
        text.text = 'CHANGED_PIN'
        with self.assertRaises(ValueError):
            prepare_svg(root, 'Core_BTB')


if __name__ == '__main__':
    unittest.main()
