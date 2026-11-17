"""Compare schematic connectivity (kicad-cli netlist) with PCB pad nets."""
import sys, re, subprocess, collections, tempfile, os
import pcbnew
sch, pcb = sys.argv[1], sys.argv[2]
tmp = tempfile.mktemp(suffix='.net')
subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadsexpr','-o',tmp,sch],check=True,capture_output=True)
txt=open(tmp).read()
snets={}
for m in re.finditer(r'\(net \(code "\d+"\) \(name "([^"]*)"\)(.*?)\)\s*(?=\(net |\)\s*\)\s*$)', txt, re.S):
    nodes=re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"', m.group(2))
    snets[m.group(1)]=frozenset(f"{r}.{p}" for r,p in nodes)
b=pcbnew.LoadBoard(pcb)
pn=collections.defaultdict(set)
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetNumber() and p.GetNetname():
            pn[p.GetNetname()].add(f"{f.GetReference()}.{p.GetNumber()}")
pnets={k:frozenset(v) for k,v in pn.items()}
def part(nets):
    m={}
    for n,s in nets.items():
        if len(s)<2: continue
        for x in s: m[x]=s
    return m
sm,pm=part(snets),part(pnets)
spins=set().union(*snets.values()); ppins=set().union(*pnets.values())
print(f"schematic: {len(snets)} nets, {len(spins)} pins; pcb: {len(pnets)} nets, {len(ppins)} pads")
sname={v:k for k,v in snets.items()}; pname={v:k for k,v in pnets.items()}
same=0; diff=[]
for s in set(snets.values()):
    if len(s)<2: continue
    ps={pm.get(x,frozenset([x])) for x in s if x in ppins}
    if len(ps)==1 and next(iter(ps))==s: same+=1
    else: diff.append(s)
print(f"multi-pin schematic nets identical on PCB: {same}; differing: {len(diff)}")
for s in sorted(diff,key=lambda s:sname[s]):
    print(f"  SCH {sname[s]}: {sorted(s)}")
    for x in sorted(s):
        if x in pm: print(f"     {x} -> PCB {pname[pm[x]]} {sorted(pm[x]-s)[:8]}")
        elif x not in ppins: print(f"     {x} -> not on PCB")
print("pins only in schematic:", sorted(spins-ppins)[:40])
print("pads only on pcb (with net):", sorted(ppins-spins)[:40])
print("--- reverse: PCB nets split across schematic nets")
for s in sorted(set(pnets.values()), key=lambda s: pname[s]):
    if len(s)<2: continue
    ss={sname[sm[x]] if x in sm else ('single' if x in spins else 'absent') for x in s}
    if len(ss)>1: print(f"  PCB {pname[s]}: -> {sorted(ss)}")
