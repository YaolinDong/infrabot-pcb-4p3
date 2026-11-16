# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YaolinDong
"""Read EasyEDA V3 per-field change logs without changing design files.

PCB coordinates are mil; schematic coordinates are 10 mil. Never infer units
from the generic V3 format introduction.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from copy import deepcopy
from pathlib import Path
import json
import math



class Document:
    def __init__(self, head, records=None):
        self.head = deepcopy(head)
        self.records = OrderedDict(records or {})

    def items(self, kind):
        return ((key[1], value) for key, value in self.records.items() if key[0] == kind)

    def attributes(self, parent):
        return {b['key']: (i, b) for i, b in self.items('ATTR') if b.get('parentId') == parent}

    def components(self):
        out = {}
        for i, b in self.items('COMPONENT'):
            attrs = self.attributes(i)
            if 'Designator' in attrs:
                out[attrs['Designator'][1]['value']] = (i, b, attrs)
        return out


class ProjectFile:
    def __init__(self, path):
        self.path = Path(path)
        self.original = self.path.read_text()
        self.docs = OrderedDict()
        self.max_ticket = 0
        events = defaultdict(list)
        key = None
        for lineno, line in enumerate(self.original.splitlines(), 1):
            if not line.strip():
                continue
            rawhead, body = line.split('||', 1)
            head = json.loads(rawhead)
            if body.endswith('|'):
                body = body[:-1]
            body = json.loads(body) if body else None
            self.max_ticket = max(self.max_ticket, head.get('ticket', 0))
            if head['type'] == 'DOCHEAD':
                key = (body['docType'], body['uuid'])
                self.docs.setdefault(key, Document(body))
                self.docs[key].head.update(body)
            else:
                assert key is not None, (self.path, lineno)
                events[key].append((head.get('ticket', 0), lineno, head, body))
        for key, rows in events.items():
            for _, _, head, body in sorted(rows):
                rkey = (head['type'], head.get('id', ''))
                if body is None or body == '':
                    self.docs[key].records.pop(rkey, None)
                else:
                    # Saved files contain partial records, including zIndex-only
                    # updates. Replacing the entire object would drop connectivity.
                    assert isinstance(body, dict), (self.path, rkey)
                    self.docs[key].records.setdefault(rkey, {}).update(deepcopy(body))
        self.baseline = deepcopy(self.docs)

    def of_type(self, kind):
        matches = [d for (t, _), d in self.docs.items() if t == kind]
        assert len(matches) == 1, (kind, len(matches))
        return matches[0]



def symbol_pins(symbol):
    out = {}
    for ident, pin in symbol.items('PIN'):
        attrs = symbol.attributes(ident)
        number = attrs.get('Pin Number', ('', {}))[1].get('value')
        if number is not None:
            out[str(number)] = (ident, pin)
    return out


def rotate(x, y, angle):
    a = math.radians(angle)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def pin_world(pin, component):
    x, y = rotate(pin['x'], pin['y'], component.get('rotation', 0))
    if component.get('isMirror'):
        x = -x
    return x + component['x'], y + component['y']


def pcb_pad_world(pad, component):
    x, y = rotate(pad['centerX'], pad['centerY'], component.get('angle', 0))
    return (x + component['x']) * .0254, (y + component['y']) * .0254


def all_pcb_pads(project):
    pcb = project.of_type('PCB')
    nets = {}
    for ident, b in pcb.items('PAD_NET'):
        key = json.loads(ident)
        nets[(key[1], key[3])] = b.get('padNet', '')
    result = []
    for ref, (ident, component, attrs) in pcb.components().items():
        fp_id = attrs['Footprint'][1]['value']
        fp = project.docs[('FOOTPRINT', fp_id)]
        for padid, pad in fp.items('PAD'):
            x, y = pcb_pad_world(pad, component)
            result.append(dict(ref=ref, component=ident, padid=padid, num=str(pad.get('num', '')),
                               net=nets.get((ident, padid), ''), x=x, y=y,
                               angle=component.get('angle', 0) + pad.get('padAngle', 0),
                               pad=deepcopy(pad)))
    for padid, pad in pcb.items('PAD'):
        result.append(dict(ref='', component='', padid=padid, num=str(pad.get('num', '')),
                           net=pad.get('netName', ''), x=pad['centerX'] * .0254,
                           y=pad['centerY'] * .0254, angle=pad.get('padAngle', 0), pad=deepcopy(pad)))
    return result
