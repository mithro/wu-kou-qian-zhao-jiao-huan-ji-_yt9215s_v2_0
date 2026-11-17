#!/usr/bin/env python3
"""Post-import fix-ups for KiCad 9.0's EasyEDA Pro importer output.

Run with KiCad's Python (needs `pcbnew`) from the KiCad project directory.
Each fix works around a specific importer problem; see kicad/README.md.

1. SMD pads: the .epro stores every SMD pad with a 0.001 mm placeholder
   hole, and KiCad's importer turns any pad with a hole into an all-layer
   PTH pad. Convert pads with a hole < 0.01 mm back to SMD pads on the
   footprint's side (copper + paste + mask), in the board and the library.
2. Footprint links: the schematic importer points every symbol at a
   footprint library called "<name>--easyedapro" that doesn't exist; the PCB
   importer wrote the footprints to "<project>.pretty". Point each symbol at
   the footprint the PCB actually uses for that reference designator.
3. Case-colliding library footprints (C0402/c0402 etc.) break checkouts on
   macOS/Windows. Drop lowercase duplicates nothing uses; rename used ones.
4. Cross-sheet net names: EasyEDA Pro net names are global, but the importer
   turns wire net names into KiCad *local* labels, which split nets that span
   both sheets (the 10 port LED nets). Local labels whose name is used on more
   than one sheet, and has no global label, become global labels.
5. Refill copper zones (the importer leaves them unfilled).
6. Design rules: the importer keeps KiCad's defaults (0.2 mm clearance), but
   the EasyEDA design rules are 4 mil (0.1016 mm) clearance, 10 mil default
   track, 24/12 mil vias. Copy those into the Default net class.
7. Footprint values: the PCB importer sets each footprint Value to its reference
   designator or leaves it empty. Copy the Value from the schematic symbol.
"""
import json
import os, re, glob, sys
import pcbnew

PRJ = sys.argv[1] if len(sys.argv) > 1 else '.'
os.chdir(PRJ)
name = os.path.basename(glob.glob('*.kicad_pro')[0])[:-len('.kicad_pro')]
pcbfile, fplib = name + '.kicad_pcb', name + '.pretty'
FPNICK = name
schs = sorted(f for f in glob.glob('*.kicad_sch') if f != name + '.kicad_sch')

TINY = pcbnew.FromMM(0.01)

def fix_pads(fp, back):
    n = 0
    for p in fp.Pads():
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and 0 < p.GetDrillSizeX() < TINY:
            p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
            p.SetDrillSize(pcbnew.VECTOR2I(0, 0))
            ls = pcbnew.LSET()
            for l in ((pcbnew.B_Cu, pcbnew.B_Paste, pcbnew.B_Mask) if back
                      else (pcbnew.F_Cu, pcbnew.F_Paste, pcbnew.F_Mask)):
                ls.AddLayer(l)
            p.SetLayerSet(ls)
            n += 1
    return n

# --- 3. case collisions in the footprint library --------------------------
board = pcbnew.LoadBoard(pcbfile)
used = {f.GetFPID().GetLibItemName().wx_str() for f in board.GetFootprints()}
mods = [os.path.basename(m)[:-10] for m in glob.glob(fplib + '/*.kicad_mod')]
rename = {}
for m in mods:
    others = [o for o in mods if o != m and o.lower() == m.lower()]
    if others and m != m.upper() and m == m.lower():
        if m in used:
            rename[m] = others[0] + '_1'
        else:
            os.remove(f'{fplib}/{m}.kicad_mod')
            print(f'removed unused case-duplicate footprint {m}')

# --- 1. pads in the board ---------------------------------------------------
npads = 0
for f in board.GetFootprints():
    npads += fix_pads(f, f.IsFlipped())
    lib = f.GetFPID().GetLibItemName().wx_str()
    if lib in rename:
        fid = f.GetFPID(); fid.SetLibItemName(pcbnew.UTF8(rename[lib])); f.SetFPID(fid)
print(f'board: {npads} SMD pads repaired')
refs = {f.GetReference(): f.GetFPIDAsString() for f in board.GetFootprints()}

# --- 5. zones ----------------------------------------------------------------
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(pcbfile, board)

# --- 1. pads in the library --------------------------------------------------
nlib = 0
libpath = os.path.abspath(fplib)
for m in [os.path.basename(x)[:-10] for x in glob.glob(fplib + '/*.kicad_mod')]:
    fp = pcbnew.FootprintLoad(libpath, m)
    k = fix_pads(fp, False)
    if m in rename:
        os.remove(f'{fplib}/{m}.kicad_mod')
        fid = fp.GetFPID(); fid.SetLibItemName(pcbnew.UTF8(rename[m])); fp.SetFPID(fid)
        print(f'renamed case-duplicate footprint {m} -> {rename[m]}')
    if k or m in rename:
        pcbnew.FootprintSave(libpath, fp)
    nlib += k
print(f'library: {nlib} SMD pads repaired')

# --- 2 & 4. schematic -------------------------------------------------------
def fp_prop(m):
    return f'(property "Footprint" "{m}"'
texts = {s: open(s, encoding='utf-8').read() for s in schs}
symre = re.compile(r'(\n\t\(symbol\n\t\t\(lib_id "[^"]+"(?:.*?))(\n\t\))', re.S)
lab = {s: set(re.findall(r'\n\t\(label "([^"]+)"', t)) for s, t in texts.items()}
glob_names = set().union(*(re.findall(r'\n\t\(global_label "([^"]+)"', t) for t in texts.values()))
multi = {n for n in set().union(*lab.values())
         if sum(n in v for v in lab.values()) > 1 and n not in glob_names}
print('labels made global:', sorted(multi))
for s, t in texts.items():
    def fix_sym(mm):
        body = mm.group(1)
        r = re.search(r'\(property "Reference" "([^"]*)"', body).group(1)
        new = refs.get(r)
        if new is None:
            cur = re.search(r'\(property "Footprint" "([^"]*)"', body).group(1)
            item = cur.split(':', 1)[1] if ':' in cur else cur
            new = f'{FPNICK}:{item}' if item else ''
        body = re.sub(r'\(property "Footprint" "[^"]*"', lambda _: fp_prop(new), body, count=1)
        return body + mm.group(2)
    t = symre.sub(fix_sym, t)
    # library-cache copies: just repoint the nickname
    t = re.sub(r'"Footprint" "[^":"]*--easyedapro:', f'"Footprint" "{FPNICK}:', t)
    t = re.sub(r'"Footprint" "' + re.escape(FPNICK) + ':"', '"Footprint" ""', t)
    def to_global(mm):
        n, rest = mm.group(1), mm.group(2)
        if n not in multi:
            return mm.group(0)
        at = re.search(r'\(at ([-\d.]+) ([-\d.]+)', rest)
        prop = (f'\n\t\t(property "Intersheetrefs" "${{INTERSHEET_REFS}}"\n\t\t\t(at {at.group(1)} {at.group(2)} 0)'
                '\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)')
        return f'\n\t(global_label "{n}"\n\t\t(shape passive){rest}{prop}\n\t)'
    t = re.sub(r'\n\t\(label "([^"]+)"(.*?)\n\t\)', to_global, t, flags=re.S)
    open(s, 'w', encoding='utf-8').write(t)

# symbol library file
for symlib in glob.glob('*.kicad_sym'):
    t = open(symlib, encoding='utf-8').read()
    t = re.sub(r'"Footprint" "[^":"]*--easyedapro:"', '"Footprint" ""', t)
    t = re.sub(r'"Footprint" "[^":"]*--easyedapro:', f'"Footprint" "{FPNICK}:', t)
    for a, b in rename.items():
        t = t.replace(f'"{FPNICK}:{a}"', f'"{FPNICK}:{b}"')
    open(symlib, 'w', encoding='utf-8').write(t)

values = {}
for s in schs:
    for mm in symre.finditer(open(s, encoding='utf-8').read()):
        r = re.search(r'\(property "Reference" "([^"]*)"', mm.group(1)).group(1)
        v = re.search(r'\(property "Value" "([^"]*)"', mm.group(1))
        if v and v.group(1):
            values[r] = v.group(1)
board = pcbnew.LoadBoard(pcbfile)
nv = 0
for f in board.GetFootprints():
    if f.GetReference() in values and f.GetValue() in ("", f.GetReference()):
        f.SetValue(values[f.GetReference()]); nv += 1
pcbnew.SaveBoard(pcbfile, board)
print(f'{nv} footprint values copied from the schematic')

pro = name + '.kicad_pro'
d = json.load(open(pro))
for c in d['net_settings']['classes']:
    if c['name'] == 'Default':
        c.update(clearance=0.1016, track_width=0.254, via_diameter=0.6096, via_drill=0.3048)
json.dump(d, open(pro, 'w'), indent=2)
print('done')
