#!/usr/bin/env python3
"""Fix the DRC and schematic-parity problems left after fixup_import.py and
fix_schematic_erc.py. Run with KiCad 9's Python from the project directory.
See kicad/README.md for why each change is safe.
"""
import collections, glob, math, os, re, subprocess, sys, tempfile
import pcbnew

os.chdir(sys.argv[1] if len(sys.argv) > 1 else '.')
name = glob.glob('*.kicad_pro')[0][:-10]
pcbfile, fplib = name + '.kicad_pcb', os.path.abspath(name + '.pretty')
b = pcbnew.LoadBoard(pcbfile)
mm = pcbnew.FromMM


def graphics_from_library(ref):
    """Give footprint ref on the board its library copy's graphics."""
    b = pcbnew.LoadBoard(pcbfile)
    old = b.FindFootprintByReference(ref)
    new = pcbnew.FootprintLoad(fplib, old.GetFPID().GetLibItemName().wx_str())
    b.Add(new)
    new.SetPosition(old.GetPosition())
    if old.IsFlipped():
        new.Flip(new.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    new.SetOrientation(old.GetOrientation())
    po = sorted((p.GetNumber(), p.GetPosition().x, p.GetPosition().y) for p in old.Pads())
    pn = sorted((p.GetNumber(), p.GetPosition().x, p.GetPosition().y) for p in new.Pads())
    assert [a[0] for a in po] == [c[0] for c in pn], ref
    assert max(max(abs(a[1] - c[1]), abs(a[2] - c[2])) for a, c in zip(po, pn)) < 1000, ref
    og, ng = list(old.GraphicalItems()), list(new.GraphicalItems())
    for g in og:
        old.Remove(g)
    for g in ng:
        new.Remove(g)
        old.Add(g)
    b.Remove(new)
    pcbnew.SaveBoard(pcbfile, b)
    os._exit(0)


if sys.argv[2:3] == ['--graphics-from-library']:
    graphics_from_library(sys.argv[3])

# --- schematic netlist ---------------------------------------------------------
tmp = tempfile.mktemp(suffix='.net')
subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '-o', tmp, name + '.kicad_sch'],
               check=True, capture_output=True)
txt = open(tmp).read()
sch_net, sch_val = {}, {}
for m in re.finditer(r'\(net \(code "\d+"\) \(name "([^"]*)"\)(.*?)\)\s*(?=\(net |\)\s*\)\s*$)', txt, re.S):
    for r, p in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"', m.group(2)):
        sch_net[(r, p)] = m.group(1)
for r, v in re.findall(r'\(comp \(ref "([^"]+)"\)\s*\(value "([^"]*)"\)', txt):
    sch_val[r] = v

# 1. USB1 shell: the USB-C footprint has two pads "1" and two pads "2" (shell
#    tabs). EasyEDA puts all four on GND; the importer only kept the net on one
#    of each pair, so GND tracks touching the other two were "shorts".
usb = b.FindFootprintByReference('USB1')
gnd = b.FindNet('GND')
n1 = 0
for p in usb.Pads():
    if p.GetNumber() in ('1', '2') and not p.GetNetname():
        p.SetNet(gnd)
        n1 += 1
print(f'1. USB1 shell pads put on GND: {n1}')

# 2. EasyEDA "no copper pour" regions (REGION type 7) were imported as full
#    keepouts (no tracks, vias or pads), so the routed tracks and pads of the buck
#    converter and crystal inside them were errors. They only keep out copper pour.
n2 = 0
for z in b.Zones():
    if z.GetIsRuleArea() and not z.GetParentFootprint():
        z.SetDoNotAllowTracks(False)
        z.SetDoNotAllowVias(False)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        z.SetDoNotAllowCopperPour(True)
        n2 += 1
print(f'2. pour-only keepouts: {n2}')

# 3. The four 3.2 mm mounting holes were imported as filled zones on Edge.Cuts,
#    which KiCad ignores, so the board had no mounting holes. Make them NPTH holes
#    (as in EasyEDA's NPTH drill file) in a MountingHole footprint.
n3 = 0
for z in list(b.Zones()):
    if z.GetLayer() == pcbnew.Edge_Cuts:
        bb = z.GetBoundingBox()
        c, d = bb.GetCenter(), bb.GetWidth()
        fp = pcbnew.FOOTPRINT(b)
        fp.SetFPID(pcbnew.LIB_ID(name, 'MountingHole_3.2mm'))
        fp.SetReference(f'MH{n3 + 1}')
        fp.SetValue('MountingHole_3.2mm')
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        fp.SetAttributes(pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        pad = pcbnew.PAD(fp)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetSize(pcbnew.VECTOR2I(d, d))
        pad.SetDrillSize(pcbnew.VECTOR2I(d, d))
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu)
        ls.AddLayer(pcbnew.F_Mask); ls.AddLayer(pcbnew.B_Mask)
        pad.SetLayerSet(ls)
        fp.Add(pad)
        cy = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
        cy.SetLayer(pcbnew.F_CrtYd)
        cy.SetCenter(pcbnew.VECTOR2I(0, 0))
        cy.SetEnd(pcbnew.VECTOR2I(d // 2 + mm(0.25), 0))
        cy.SetWidth(mm(0.05))
        fp.Add(cy)
        b.Add(fp)
        fp.SetPosition(c)
        b.Remove(z)
        n3 += 1
if n3:
    pcbnew.FootprintSave(fplib, fp)
print(f'3. mounting holes restored: {n3}')

# 4. RJ45 plastic pegs: drawn as circular Edge.Cuts polygons in the jack
#    footprint. EasyEDA drills them as 3.25 mm NPTH holes; make them NPTH pads so
#    hole (not board-edge) clearance rules apply.
def pegs_to_npth(fp):
    n = 0
    for g in list(fp.GraphicalItems()):
        if g.GetLayer() == pcbnew.Edge_Cuts and g.GetShape() == pcbnew.SHAPE_T_POLY:
            bb = g.GetBoundingBox()
            d = bb.GetWidth()
            if abs(bb.GetWidth() - bb.GetHeight()) > mm(0.01):
                continue
            pad = pcbnew.PAD(fp)
            pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
            pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
            pad.SetSize(pcbnew.VECTOR2I(d, d))
            pad.SetDrillSize(pcbnew.VECTOR2I(d, d))
            ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu)
            ls.AddLayer(pcbnew.F_Mask); ls.AddLayer(pcbnew.B_Mask)
            pad.SetLayerSet(ls)
            fp.Add(pad)
            pad.SetPosition(bb.GetCenter())
            fp.Remove(g)
            n += 1
    return n


n4 = sum(pegs_to_npth(f) for f in b.GetFootprints())
print(f'4. RJ45 peg holes made NPTH pads: {n4}')

# 5. Duplicate vias (same place, same net) are drilled twice; keep one.
seen, dup = set(), []
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        k = (t.GetPosition().x, t.GetPosition().y, t.GetNetCode())
        if k in seen:
            dup.append(t)
        seen.add(k)
for t in dup:
    b.Remove(t)
print(f'5. duplicate vias removed: {len(dup)}')

# 6. U2's exposed GND pad is a free-standing pad on the board ("Pad_e346"), not
#    part of a schematic symbol. Mark it board-only and put it in the library.
for f in b.GetFootprints():
    if f.GetFPID().GetLibItemName().wx_str().startswith('Pad_') and not f.GetReference():
        f.SetReference('EP1')
        f.Reference().SetVisible(False)
        f.SetValue('U2 exposed pad')
        f.Value().SetVisible(False)
        f.SetBoardOnly(True)
        f.SetExcludedFromBOM(True)
        f.SetExcludedFromPosFiles(True)
        pcbnew.FootprintSave(fplib, f)
        print(f'6. {f.GetFPIDAsString()} marked board-only (EP1)')

# 7. The board title uses "Century Gothic", which isn't installed, and the
#    substituted font is too thin for silkscreen. Use KiCad's stroke font.
for d in b.GetDrawings():
    if d.GetClass() == 'PCB_TEXT' and 'Century Gothic' in d.GetFontName():
        d.SetFont(None)
        d.SetTextThickness(max(d.GetTextThickness(), mm(0.15)))
        print(f'7. text "{d.GetText()}" uses the KiCad font')

# 8. Net names and values as in the schematic ("Update PCB from Schematic").
rename = collections.defaultdict(collections.Counter)
for f in b.GetFootprints():
    for p in f.Pads():
        k = (f.GetReference(), p.GetNumber())
        if k in sch_net and p.GetNetname():
            rename[p.GetNetname()][sch_net[k]] += 1
nets = b.GetNetsByName()
n8 = 0
for old, c in rename.items():
    new = c.most_common(1)[0][0]
    assert len(c) == 1, (old, c)
    if new != old:
        nets[old].SetNetname(new)
        n8 += 1
nv = 0
for f in b.GetFootprints():
    r = f.GetReference()
    if r in sch_val and f.GetValue() != sch_val[r]:
        f.SetValue(sch_val[r])
        nv += 1
print(f'8. nets renamed: {n8}; values updated: {nv}')

# 9. Pads with a single thermal spoke into the GND pour: connect them solidly.
for ref, num in (('RJ5', 'SHIELD0'), ('X1', '2'), ('C21', '1')):
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == num:
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
print('9. solid zone connection on RJ5.SHIELD0, X1.2, C21.1')


# 10. Pins the schematic leaves unconnected get KiCad's own "unconnected-(...)"
#     nets, as Update PCB from Schematic would give them.
n10 = 0
for f in b.GetFootprints():
    for p in f.Pads():
        k = (f.GetReference(), p.GetNumber())
        if not p.GetNetname() and sch_net.get(k, '').startswith('unconnected-('):
            net = pcbnew.NETINFO_ITEM(b, sch_net[k])
            b.Add(net)
            p.SetNet(net)
            n10 += 1
print(f'10. unconnected pins given their schematic net: {n10}')

# 11. Crystal X1: its GND pads 2 and 4 are joined to each other by a track but
#     nothing else, in EasyEDA too (no pour reaches them). Add a GND via from pad
#     2 to the bottom GND pour.
x1p2 = [p for p in b.FindFootprintByReference('X1').Pads() if p.GetNumber() == '2'][0]
vpos = pcbnew.VECTOR2I(mm(133.170), mm(87.244))
via = pcbnew.PCB_VIA(b)
via.SetPosition(vpos)
via.SetWidth(mm(0.6096))
via.SetDrill(mm(0.3048))
via.SetNet(gnd)
b.Add(via)
tr = pcbnew.PCB_TRACK(b)
tr.SetStart(x1p2.GetPosition())
tr.SetEnd(vpos)
tr.SetWidth(mm(0.254))
tr.SetLayer(pcbnew.F_Cu)
tr.SetNet(gnd)
b.Add(tr)
print('11. GND via added for X1 pads 2/4')

# 12. Adjacent RJ45 jacks share their shield holes (EasyEDA drills them twice).
#     RJ3 sits 0.034 mm left of the 16.002 mm pitch the other jacks use, so its
#     shield holes are 0.034 mm off RJ2's and RJ4's. Move RJ3 (and the track ends
#     on its pads) onto the pitch.
rj3 = b.FindFootprintByReference('RJ3')
dx = (b.FindFootprintByReference('RJ2').GetPosition().x + b.FindFootprintByReference('RJ4').GetPosition().x) // 2 \
    - rj3.GetPosition().x
pads3 = list(rj3.Pads())
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        continue
    for get, put in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
        e = get()
        if any(p.HitTest(e) for p in pads3):
            put(pcbnew.VECTOR2I(e.x + dx, e.y))
rj3.Move(pcbnew.VECTOR2I(dx, 0))
print(f'12. RJ3 moved {pcbnew.ToMM(dx):.3f} mm onto the jack pitch')

# 13. The JLC order-number placeholder text sat on U2's exposed pad (silk over
#     solder mask opening). Move it to a free area near the board title.
for d in b.GetDrawings():
    if d.GetClass() == 'PCB_TEXT' and d.GetText() == 'JLCJLCJLCJLC':
        d.SetPosition(pcbnew.VECTOR2I(mm(115.75), mm(77.3)))
print('13. JLC order-number text moved off U2')

# 13b. Test pad TP10 overlapped C43's silkscreen outline. It hangs off C43 pad 2
#      on a short track; move it 0.3 mm further out along that track.
tp10 = b.FindFootprintByReference('TP10')
tpad = list(tp10.Pads())[0]
for t in b.GetTracks():
    if t.GetClass() != 'PCB_VIA' and t.GetStart() == tpad.GetPosition():
        t.SetStart(pcbnew.VECTOR2I(t.GetStart().x, t.GetStart().y - mm(0.3)))
tp10.Move(pcbnew.VECTOR2I(0, -mm(0.3)))
print('13b. TP10 moved 0.3 mm off C43')

# 14. Board edge clearance: EasyEDA's rule is 11.8 mil (0.3 mm), not KiCad's
#     default 0.5 mm.
b.GetDesignSettings().m_CopperEdgeClearance = mm(0.29972)
print('14. copper to board edge clearance 11.8 mil')


# --- silkscreen clipping ------------------------------------------------------
def mask_polys(fps):
    out = []
    for f in fps:
        for p in f.Pads():
            for layer in (pcbnew.F_Mask, pcbnew.B_Mask):
                if p.IsOnLayer(layer):
                    ps = pcbnew.SHAPE_POLY_SET()
                    p.TransformShapeToPolygon(ps, layer, 0, mm(0.005), pcbnew.ERROR_OUTSIDE)
                    out.append((layer, ps))
    return out


def clip_silk(f, polys, xmax=None, margin=mm(0.05), step=mm(0.01)):
    """Cut the parts of f's silkscreen lines that come within margin of a mask
    opening (or past x = xmax). Returns the number of lines changed."""
    n = 0
    for g in list(f.GraphicalItems()):
        if g.GetClass() != 'PCB_SHAPE' or g.GetShape() != pcbnew.SHAPE_T_SEGMENT:
            continue
        if g.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            continue
        mlayer = pcbnew.F_Mask if g.GetLayer() == pcbnew.F_SilkS else pcbnew.B_Mask
        a, e, w = g.GetStart(), g.GetEnd(), g.GetWidth()
        L = math.hypot(e.x - a.x, e.y - a.y)
        k = max(int(L / step), 1)
        pts = [pcbnew.VECTOR2I(int(a.x + (e.x - a.x) * i / k), int(a.y + (e.y - a.y) * i / k)) for i in range(k + 1)]
        bad = [any(l == mlayer and ps.Collide(q, w // 2 + margin) for l, ps in polys)
               or (xmax is not None and q.x + w // 2 > xmax) for q in pts]
        if not any(bad):
            continue
        n += 1
        runs, cur = [], []
        for q, bd in zip(pts, bad):
            if bd:
                if len(cur) > 1:
                    runs.append((cur[0], cur[-1]))
                cur = []
            else:
                cur.append(q)
        if len(cur) > 1:
            runs.append((cur[0], cur[-1]))
        for s0, s1 in runs:
            if math.hypot(s1.x - s0.x, s1.y - s0.y) < w:
                continue
            ng = pcbnew.PCB_SHAPE(f, pcbnew.SHAPE_T_SEGMENT)
            ng.SetLayer(g.GetLayer())
            ng.SetWidth(w)
            ng.SetStart(s0)
            ng.SetEnd(s1)
            f.Add(ng)
        f.Remove(g)
    return n


# 15. USB1's receptacle overhangs the board edge; its outline was drawn on the
#     edge line. DC1's outline runs over RJ5's shield pad. Clip both (each is
#     used once, so the library copy is updated from the board in step 18).
edge_x = b.GetBoardEdgesBoundingBox().GetRight()
usb = b.FindFootprintByReference('USB1')
n15 = clip_silk(usb, mask_polys([usb]), xmax=edge_x - mm(0.2))
dc1 = b.FindFootprintByReference('DC1')
n15 += clip_silk(dc1, mask_polys([dc1, b.FindFootprintByReference('RJ5')]))
print(f'15. USB1/DC1 silkscreen lines clipped: {n15}')

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(pcbfile, b)

# --- library footprints -------------------------------------------------------
# 16. RJ45 jack: the board copy has the peg holes as NPTH pads (step 4); make it
#     the library footprint, then fix its silkscreen and courtyard there. The
#     jacks are ganged at a 16.002 mm pitch with shared shield holes at x = ±8.001,
#     so the outline's side lines (on x = ±8.001) overlapped the next jack's and
#     ran over the shield pads, and the courtyard (±9.33) overlapped the next jack
#     and DC1. Side lines move in to ±7.85 and break around the shield pads; the
#     courtyard follows the body (±8.001).
b2 = pcbnew.LoadBoard(pcbfile)
rj = b2.FindFootprintByReference('RJ1')
rj.SetOrientationDegrees(0)
rj.SetPosition(pcbnew.VECTOR2I(0, 0))
X = mm(8.001)
XI = mm(7.85)
for g in list(rj.GraphicalItems()):
    if g.GetClass() != 'PCB_SHAPE':
        continue
    if g.GetLayer() == pcbnew.F_SilkS and g.GetShape() == pcbnew.SHAPE_T_SEGMENT:
        a, e = g.GetStart(), g.GetEnd()
        clamp = lambda v: pcbnew.VECTOR2I(max(-XI, min(XI, v.x)), v.y)
        g.SetStart(clamp(a))
        g.SetEnd(clamp(e))
    elif g.GetLayer() == pcbnew.F_CrtYd and g.GetShape() == pcbnew.SHAPE_T_RECT:
        a, e = g.GetStart(), g.GetEnd()
        g.SetStart(pcbnew.VECTOR2I(-X if a.x < 0 else X, a.y))
        g.SetEnd(pcbnew.VECTOR2I(-X if e.x < 0 else X, e.y))
clip_silk(rj, mask_polys([rj]))
for p in rj.Pads():
    p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_INHERITED)
pcbnew.PCB_IO_KICAD_SEXPR().FootprintSave(fplib, rj)

# 17. USB-C, DC jack: save the board's clipped copies (one instance each).
for ref in ('USB1', 'DC1'):
    f = b2.FindFootprintByReference(ref)
    if f.IsFlipped():
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    f.SetOrientationDegrees(0)
    f.SetPosition(pcbnew.VECTOR2I(0, 0))
    pcbnew.PCB_IO_KICAD_SEXPR().FootprintSave(fplib, f)


def edit_lib(item, fn):
    f = pcbnew.FootprintLoad(fplib, item)
    fn(f)
    pcbnew.PCB_IO_KICAD_SEXPR().FootprintSave(fplib, f)


# 18. Test points are bare 0.5 mm pads with no part body; their 1 mm courtyard
#     only produced overlaps with the parts they sit next to. Remove it.
def no_courtyard(f):
    for g in list(f.GraphicalItems()):
        if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            f.Remove(g)


for item in ('Test-Point-0.5mm', 'Test-Point-0.5mm_1'):
    edit_lib(item, no_courtyard)


# 19. 6.3 mm electrolytic C2/C6: the pads are 0.21 mm apart (as in EasyEDA) and
#     the bodies 2.4 mm apart, but the courtyards (0.25 mm past the pads)
#     overlapped. Use IPC-7351's 0.1 mm ("least") courtyard excess.
def tight_courtyard(f):
    xr = max(int(p.GetBoundingBox().GetRight()) for p in f.Pads()) + mm(0.1)
    for g in f.GraphicalItems():
        if g.GetLayer() == pcbnew.F_CrtYd and g.GetShape() == pcbnew.SHAPE_T_RECT:
            a, e = g.GetStart(), g.GetEnd()
            g.SetStart(pcbnew.VECTOR2I(-xr if a.x < 0 else xr, a.y))
            g.SetEnd(pcbnew.VECTOR2I(-xr if e.x < 0 else xr, e.y))


edit_lib('CAP-SMD_BD6.3-L6.6-W6.6-LS7.4-FD', tight_courtyard)

# 20. Board footprints that differ from their library copy: EasyEDA stores each
#     placed footprint separately, and rotating them left sub-micron differences
#     (arc midpoints, rectangles stored as polygons). Replace each instance's
#     graphics with the library's (pads are checked to match within 1 um), which
#     is what Update Footprints from Library does. The SWIG wrappers get confused
#     after removing items, so each footprint is done in a fresh process.
b = pcbnew.LoadBoard(pcbfile)
todo = []
for f in b.GetFootprints():
    lib = pcbnew.FootprintLoad(fplib, f.GetFPID().GetLibItemName().wx_str())
    if lib is None or f.FootprintNeedsUpdate(lib):
        todo.append(f.GetReference())
for ref in todo:
    subprocess.run([sys.executable, os.path.abspath(__file__), '.', '--graphics-from-library', ref], check=True,
                   stderr=subprocess.DEVNULL)
b = pcbnew.LoadBoard(pcbfile)
left = [f.GetReference() for f in b.GetFootprints()
        if f.FootprintNeedsUpdate(pcbnew.FootprintLoad(fplib, f.GetFPID().GetLibItemName().wx_str()))]
print(f'20. footprints given their library graphics: {len(todo)}; still different: {left}')
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(pcbfile, b)

# 21. What is left is the four shield holes that neighbouring RJ45 jacks share
#     (RJ1.SHIELD0 = RJ2.SHIELD1 and so on). That is how the jacks are ganged in
#     the original design, and EasyEDA's drill file drills each of them twice
#     too, so record them as reviewed DRC exclusions rather than change the
#     footprints. KiCad matches an exclusion by rule, marker position (the hole
#     centre) and the two pads, in the order its DRC reports them.
import json
proj = name + '.kicad_pro'
tmp = tempfile.mktemp(suffix='.json')
subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', tmp, pcbfile], check=True, capture_output=True)
pads = {p.m_Uuid.AsString(): p for f in b.GetFootprints() for p in f.Pads()}
ex = []
for v in json.load(open(tmp))['violations']:
    if v['type'] != 'holes_co_located':
        continue
    a, c = (pads[i['uuid']] for i in v['items'])
    assert {a.GetNumber(), c.GetNumber()} == {'SHIELD0', 'SHIELD1'} and a.GetPosition() == c.GetPosition()
    refs = ' / '.join(f'{p.GetParentFootprint().GetReference()}.{p.GetNumber()}' for p in (a, c))
    ex.append([f'holes_co_located|{a.GetPosition().x}|{a.GetPosition().y}|{a.m_Uuid.AsString()}|{c.m_Uuid.AsString()}',
               f'{refs}: ganged RJ45 jacks share one shield hole, as in the EasyEDA design'])
pro = json.load(open(proj))
pro['board']['design_settings']['drc_exclusions'] = sorted(ex)
with open(proj, 'w') as fh:
    json.dump(pro, fh, indent=2)
print(f'21. shared RJ45 shield holes recorded as DRC exclusions: {len(ex)}')
