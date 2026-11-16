# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YaolinDong
import csv,hashlib,io,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify import ROOT,PROJECT,verify,verify_manifest,check_assembly,read_csv

class ReleaseTests(unittest.TestCase):
    def test_current_public_release(self):
        result=verify();self.assertTrue(result['passed'],result['errors'])
        self.assertEqual((result['components'],result['assigned_pin_connections'],result['component_pads']),(105,338,475))
    def test_manifest_rejects_missing_and_changed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x';p.write_bytes(b'good')
            m={'schema':'infrabot-public-release-v1','files':[{'path':'x','bytes':4,'sha256':hashlib.sha256(b'good').hexdigest()}]}
            self.assertEqual(verify_manifest(tmp,m),[])
            p.write_bytes(b'evil');self.assertTrue(verify_manifest(tmp,m))
            p.unlink();self.assertTrue(verify_manifest(tmp,m))
    def test_manifest_rejects_path_escape(self):
        m={'schema':'infrabot-public-release-v1','files':[{'path':'../outside','bytes':0,'sha256':'0'*64}]}
        self.assertTrue(any('escapes' in e for e in verify_manifest(ROOT,m)))
    def modified_tables(self,change_bom=None,change_cpl=None):
        with tempfile.TemporaryDirectory() as tmp:
            b=read_csv(ROOT/'manufacturing/R8/BOM.csv');c=read_csv(ROOT/'manufacturing/R8/CPL.csv')
            if change_bom:change_bom(b)
            if change_cpl:change_cpl(c)
            paths=[]
            for name,rows in [('BOM.csv',b),('CPL.csv',c)]:
                p=Path(tmp)/name;paths.append(p)
                with p.open('w',encoding='utf-8-sig',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
            return check_assembly(ROOT/PROJECT,*paths)
    def test_duplicate_designator_rejected(self):
        def duplicate(rows):rows[1]['Designator']=rows[0]['Designator']
        self.assertFalse(self.modified_tables(change_bom=duplicate)['passed'])
    def test_wrong_placement_rotation_rejected(self):
        def rotate(rows):rows[0]['Rotation']=str(float(rows[0]['Rotation'])+90)
        result=self.modified_tables(change_cpl=rotate)
        self.assertTrue(any('rotation' in e for e in result['errors']))
    def test_wrong_assembly_side_rejected(self):
        def bottom(rows):rows[0]['Layer']='B'
        self.assertFalse(self.modified_tables(change_cpl=bottom)['passed'])

if __name__=='__main__':unittest.main()
