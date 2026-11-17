#!/usr/bin/env python3
"""Compare schematic connectivity (kicad-cli netlist) with the PCB's pad nets.

Usage: compare_nets.py <project>.kicad_sch <project>.kicad_pcb

Every pin is assigned to a group on each side (its net, or a group of its own
if it is unconnected). The two partitions of the pins present on both sides are
compared; any schematic net that is split or merged on the PCB is listed.
"""
import collections, re, subprocess, sys, tempfile
import pcbnew

sch, pcb = sys.argv[1], sys.argv[2]
tmp = tempfile.mktemp(suffix='.net')
subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', tmp, sch],
               check=True, capture_output=True)
txt = open(tmp).read()
snet = {}
for m in re.finditer(r'\(net \(code "\d+"\) \(name "([^"]*)"\)(.*?)\)\s*(?=\(net |\)\s*\)\s*$)', txt, re.S):
    for r, p in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"', m.group(2)):
        snet[f'{r}.{p}'] = m.group(1)

b = pcbnew.LoadBoard(pcb)
pnet = {}
for f in b.GetFootprints():
    for p in f.Pads():
        if not p.GetNumber():
            continue
        k = f'{f.GetReference()}.{p.GetNumber()}'
        n = p.GetNetname()
        if k in pnet and pnet[k] != n:   # several pads with one number
            n = pnet[k] if n == '' else n
        pnet[k] = n or f'<unconnected {k}>'

both = sorted(set(snet) & set(pnet))
print(f'schematic pins: {len(snet)}, PCB pads (by number): {len(pnet)}, compared: {len(both)}')
print('only in schematic:', sorted(set(snet) - set(pnet)))
print('only on PCB:', sorted(set(pnet) - set(snet)))


def groups(m):
    g = collections.defaultdict(set)
    for k in both:
        g[m[k]].add(k)
    return {k: frozenset(v) for k, v in g.items()}


sg, pg = groups(snet), groups(pnet)
pset = set(pg.values())
bad = [(n, s) for n, s in sorted(sg.items()) if s not in pset]
print(f'schematic nets: {len(sg)}; identical on the PCB: {len(sg) - len(bad)}; different: {len(bad)}')
for n, s in bad:
    print(f'  {n}: {sorted(s)}')
    for x in sorted(s):
        other = pg[pnet[x]] - s
        if other:
            print(f'    {x} is on PCB net {pnet[x]} which also has {sorted(other)[:10]}')
