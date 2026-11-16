#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YaolinDong
"""Create a complete local release ZIP after offline verification."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from verify import ROOT,verify

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=ROOT/'.build/infrabot-pcb-4p3-R8.zip');args=ap.parse_args()
    result=verify()
    if not result['passed']:raise SystemExit(json.dumps(result,ensure_ascii=False))
    dest=args.output.resolve()
    if dest.exists():raise SystemExit('Output exists; choose a new filename to preserve the previous release')
    dest.parent.mkdir(parents=True,exist_ok=True)
    directories={'hardware','manufacturing','verification','docs','tools','tests','LICENSES','.github'}
    root_files={'README.md','README.zh-CN.md','LICENSE','THIRD_PARTY.md','CONTRIBUTING.md','CHANGELOG.md','.gitignore','.gitattributes'}
    paths=[p for p in ROOT.rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and (p.relative_to(ROOT).parts[0] in directories or p.relative_to(ROOT).as_posix() in root_files) and p.suffix not in {'.pyc','.pyo'}]
    with zipfile.ZipFile(dest,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(paths):z.write(p,'infrabot-pcb-4p3/'+p.relative_to(ROOT).as_posix())
    checksum=hashlib.sha256(dest.read_bytes()).hexdigest();dest.with_suffix(dest.suffix+'.sha256').write_text(checksum+'  '+dest.name+'\n')
    print(json.dumps({'archive':str(dest),'files':len(paths),'bytes':dest.stat().st_size,'sha256':checksum},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
