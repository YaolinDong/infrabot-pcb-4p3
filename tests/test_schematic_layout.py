# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YaolinDong
"""Electrical and ground-symbol safeguards for schematic-only layout changes."""
import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from layout_schematics import ROOT,SOURCE,LAYOUT,Page,apply_page,encode
from check_connectivity import schematic_connections
from schematic_adjustments import apply_adjustments
from collections import defaultdict

class SchematicLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=json.loads((ROOT/'verification/expected-netlist.json').read_text())
        cls.nets={c['ref']:c['pins'] for group in source.values() for c in group}
        cls.net_blocks=defaultdict(set)
        for sheet,blocks in LAYOUT.items():
            for i,(_,_,parts,_) in enumerate(blocks):
                for ref in parts:
                    for net in cls.nets[ref].values():cls.net_blocks[net].add((sheet,i))
    def test_relayout_preserves_all_assigned_pin_networks_and_part_values(self):
        for sheet,blocks in LAYOUT.items():
            if not blocks:continue
            page=Page(SOURCE/(sheet+'.esch2'),self.nets)
            values={ref:{k:v['value'] for k,(_,v) in attrs.items()} for ref,(_,_,attrs) in page.parts.items()}
            apply_page(page,blocks,self.net_blocks)
            apply_adjustments(page.p,sheet)
            actual,ambiguous=schematic_connections(page.p)
            expected={(ref,pin):net for ref in page.parts for pin,net in self.nets[ref].items()}
            self.assertEqual(actual,expected,sheet);self.assertFalse(ambiguous,sheet)
            for ref,(_,_,attrs) in page.parts.items():self.assertEqual(values[ref],{k:v['value'] for k,(_,v) in attrs.items()},ref)
    def test_ground_symbols_are_placed_at_each_vertical_ground_branch(self):
        p=Page(SOURCE/'Power.esch2',self.nets);apply_page(p,LAYOUT['Power'],self.net_blocks)
        locations={(c['x'],c['y']) for cid,c in p.d.items('COMPONENT') if p.d.attributes(cid).get('Global Net Name',('',{}))[1].get('value')=='GND'}
        for ref in ['C1','C2','C5','C6','C9','C10','C26']:
            point=next(v['anchor'] for (r,n),v in p.pin_data.items() if r==ref and v['net']=='GND')
            self.assertIn(point,locations,ref)
        self.assertGreater(len(locations),5)
    def test_electrical_changes_in_input_are_rejected(self):
        from native_project import ProjectFile
        original=ProjectFile(SOURCE/'Core_BTB.esch2');d=original.of_type('SCH_PAGE')
        aid,value=next((i,dict(v)) for i,v in d.items('ATTR') if v.get('key')=='NET' and v.get('value')=='BOOT0');value['value']='UNEXPECTED_BOOT_NET'
        data=original.original+'\n'+encode({'type':'DOCHEAD','ticket':original.max_ticket+1},d.head)+'\n'+encode({'type':'ATTR','id':aid,'ticket':original.max_ticket+2},value)+'\n'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'Core_BTB.esch2';p.write_text(data)
            with self.assertRaises(ValueError):Page(p,self.nets)

if __name__=='__main__':unittest.main()
