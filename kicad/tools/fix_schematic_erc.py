#!/usr/bin/env python3
"""Fix the ERC problems left after fixup_import.py (run that first).

Run from the KiCad project directory with KiCad 9's kicad-cli on PATH.
See kicad/README.md for why each change is safe.

1. Net names: EasyEDA net names and net ports are global across sheets. Local
   labels whose name also appears on another sheet, or as a global label,
   become global labels (the 40 Ethernet MDI nets were split between the
   switch-chip sheet and the RJ45 sheet).
2. Pin types: EasyEDA symbols give every pin the default type "IN", which the
   importer turns into KiCad "input" pins. They carry no design intent, so
   they become "passive".
3. Wire stubs: EasyEDA draws a net label part-way along (or just past the
   end of) a wire. Trim or extend the free wire end to the label.
4. No-connect flags on U2 pins that are unconnected in both the schematic and
   the PCB.
5. Power ports: one power symbol per net with its pin named after the net
   (the importer named every port's pin after the first net it saw), then a
   PWR_FLAG on each power net that has no driving pin, as KiCad requires.
6. Test points get the value "TestPoint"; the two drawing-frame symbols
   are excluded from the board and BOM.
7. Two symbols (MT2492, Sheet-Symbol_A4) exist in two different versions
   with the same name; the schematic's version is added to the library under
   its own name.
"""
import json, os, re, subprocess, sys, tempfile, uuid

os.chdir(sys.argv[1] if len(sys.argv) > 1 else '.')
name = [f for f in os.listdir('.') if f.endswith('.kicad_pro')][0][:-10]
root = name + '.kicad_sch'
sheets = {'/P1/': '1_P1.kicad_sch', '/P2/': '2_P2.kicad_sch'}
symlib = [f for f in os.listdir('.') if f.endswith('.kicad_sym')][0]
libnick = symlib[:-10]


def read(f):
    return open(f, encoding='utf-8').read()


def write(f, t):
    open(f, 'w', encoding='utf-8').write(t)


def erc():
    out = tempfile.mktemp(suffix='.json')
    subprocess.run(['kicad-cli', 'sch', 'erc', '--format', 'json', '-o', out, root],
                   check=True, capture_output=True)
    d = json.load(open(out))
    scale = 100.0  # kicad-cli 9 reports ERC positions in units of 100 mm
    res = []
    for sh in d['sheets']:
        for v in sh['violations']:
            for it in v['items']:
                it['x'] = round(it['pos']['x'] * scale, 4)
                it['y'] = round(it['pos']['y'] * scale, 4)
            res.append((sh['path'], v))
    return res


def U():
    return str(uuid.uuid4())


# --- 1. labels -------------------------------------------------------------
texts = {p: read(f) for p, f in sheets.items()}
local = {p: set(re.findall(r'\n\t\(label "([^"]+)"', t)) for p, t in texts.items()}
glob = set().union(*(re.findall(r'\n\t\(global_label "([^"]+)"', t) for t in texts.values()))
make_global = {n for n in set().union(*local.values())
               if n in glob or sum(n in v for v in local.values()) > 1}


def to_global(mm):
    n, rest = mm.group(1), mm.group(2)
    if n not in make_global:
        return mm.group(0)
    at = re.search(r'\(at ([-\d.]+) ([-\d.]+)', rest)
    prop = (f'\n\t\t(property "Intersheetrefs" "${{INTERSHEET_REFS}}"\n\t\t\t(at {at.group(1)} {at.group(2)} 0)'
            '\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)')
    return f'\n\t(global_label "{n}"\n\t\t(shape passive){rest}{prop}\n\t)'


for p in texts:
    texts[p] = re.sub(r'\n\t\(label "([^"]+)"(.*?)\n\t\)', to_global, texts[p], flags=re.S)
print(f'1. {len(make_global)} net names made global')

# --- 2. pin types ------------------------------------------------------------
for p in texts:
    texts[p] = texts[p].replace('(pin input ', '(pin passive ')
write(symlib, read(symlib).replace('(pin input ', '(pin passive '))
for p, f in sheets.items():
    write(f, texts[p])
print('2. input pins -> passive')

# --- 3. wire stubs -------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sch_geometry
WIRE = re.compile(r'(\n\t\(wire\n\t\t\(pts\n\t\t\t)\(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)'
                  r'(\n\t\t\)(?:(?!\n\t\().)*?\(uuid "([^"]+)"\)\n\t\))', re.S)
LABEL = re.compile(r'(\n\t\((?:label|global_label|hierarchical_label) "([^"]+)"\s*(?:\(shape \w+\)\s*)?\(at )([-\d.]+) ([-\d.]+)')


def on_seg(px, py, x1, y1, x2, y2):
    return (abs(x1 - x2) < 1e-6 and abs(px - x1) < 1e-3 and min(y1, y2) - 1e-3 <= py <= max(y1, y2) + 1e-3) or \
           (abs(y1 - y2) < 1e-6 and abs(py - y1) < 1e-3 and min(x1, x2) - 1e-3 <= px <= max(x1, x2) + 1e-3)


def fix_stubs(t, flagged, log):
    wires = [(m.group(7),) + tuple(map(float, m.group(2, 3, 4, 5))) for m in WIRE.finditer(t)]
    labels = [(m.group(2), float(m.group(3)), float(m.group(4))) for m in LABEL.finditer(t)]
    pts = {}

    def add(x, y, who):
        pts.setdefault((round(x, 3), round(y, 3)), set()).add(who)
    for u, x1, y1, x2, y2 in wires:
        add(x1, y1, u)
        add(x2, y2, u)
    for n, x, y in labels:
        add(x, y, 'label')
    for x, y in re.findall(r'\((?:junction|no_connect)\s*\(at ([-\d.]+) ([-\d.]+)', t):
        add(float(x), float(y), 'j')
    for ref, num, x, y in sch_geometry.sym_pins(t):
        add(x, y, 'pin')

    def connected(x, y, u):
        if pts.get((round(x, 3), round(y, 3)), set()) - {u}:
            return True
        return any(on_seg(x, y, a, b, c, d) for w, a, b, c, d in wires if w != u)

    edits = []
    for u, x1, y1, x2, y2 in wires:
        if u not in flagged:
            continue
        c1, c2 = connected(x1, y1, u), connected(x2, y2, u)
        if c1 == c2:
            log.append(('not fixed', u, (x1, y1, x2, y2)))
            continue
        (fx, fy), (cx, cy) = ((x2, y2), (x1, y1)) if c1 else ((x1, y1), (x2, y2))
        inner = [l for l in labels if on_seg(l[1], l[2], x1, y1, x2, y2)
                 and (round(l[1], 3), round(l[2], 3)) != (round(cx, 3), round(cy, 3))]
        if inner:   # label part-way along the wire: move the label to the free end
            n, lx, ly = inner[0]
            edits.append(('label', n, lx, ly, fx, fy))
            log.append(('label moved to wire end', n))
            continue
        best = None  # label just past the free end, on the same line: extend
        for n, lx, ly in labels:
            if abs(fx - cx) < 1e-6 and abs(lx - fx) < 1e-3:
                d0, dl = fy - cy, ly - cy
            elif abs(fy - cy) < 1e-6 and abs(ly - fy) < 1e-3:
                d0, dl = fx - cx, lx - cx
            else:
                continue
            if d0 and dl * d0 > 0 and abs(d0) < abs(dl) <= abs(d0) + 5.08 + 1e-6:
                if best is None or abs(dl) < abs(best[0]):
                    best = (dl, n, lx, ly)
        if best:
            edits.append(('wire', u, cx, cy, best[2], best[3]))
            log.append(('wire extended to label', best[1]))
        else:       # a stub going nowhere: drop it
            edits.append(('drop', u))
            log.append(('dangling stub removed', u))
    for e in edits:
        if e[0] == 'label':
            _, n, lx, ly, fx, fy = e
            pat = re.compile(r'(\n\t\((?:label|global_label|hierarchical_label) "' + re.escape(n) +
                             r'"\s*(?:\(shape \w+\)\s*)?\(at )' + re.escape(f'{lx:g}') + ' ' + re.escape(f'{ly:g}'))
            t, k = pat.subn(lambda m: m.group(1) + f'{fx:g} {fy:g}', t, count=1)
            assert k == 1, e
        elif e[0] == 'drop':
            t = WIRE.sub(lambda m: '' if m.group(7) == e[1] else m.group(0), t)
        else:
            _, u, cx, cy, lx, ly = e
            t = WIRE.sub(lambda m: m.group(0) if m.group(7) != u else
                         f'{m.group(1)}(xy {cx:g} {cy:g}) (xy {lx:g} {ly:g}){m.group(6)}', t)
    return t, len(edits)


def run_stubs(tag):
    log = []
    for _ in range(5):
        viol = erc()
        changed = 0
        for p, f in sheets.items():
            # (kicad-cli 9 can file a violation under the wrong sheet, so match by uuid)
            flagged = {v['items'][0]['uuid'] for sp, v in viol
                       if v['type'] == 'unconnected_wire_endpoint'}
            t, k = fix_stubs(read(f), flagged, log)
            write(f, t)
            changed += k
        if not changed:
            break
    print(tag, 'wire stubs:', {k: sum(1 for x in log if x[0] == k) for k in {x[0] for x in log}},
          [x for x in log if x[0] == 'not fixed'])


run_stubs('3.')

# --- 4. no-connects -------------------------------------------------------------
viol = erc()
nc = {p: [] for p in sheets}
for p, v in viol:
    it = v['items'][0]
    if v['type'] == 'pin_not_connected' and p in nc:   # all on U2, sheet P1
        nc[p].append((it['x'], it['y']))
for p, f in sheets.items():
    t = read(f)
    add = ''.join(f'\n\t(no_connect\n\t\t(at {x:g} {y:g})\n\t\t(uuid "{U()}")\n\t)' for x, y in nc[p])
    t = t.replace('\n\t(wire\n', add + '\n\t(wire\n', 1)
    write(f, t)
print(f'4. no-connect flags: {sum(len(v) for v in nc.values())}')

# --- 5a. power symbols ---------------------------------------------------------
# EasyEDA reuses one power-port symbol for every net (the net comes from its
# value), but the importer gave each symbol a single hidden pin named after the
# first net it saw ("AVDDL" for every 3V3/VBUS/... port). Give every power net
# its own power symbol whose pin is named after the net, as in KiCad's power
# library, and annotate the #PWR references.
lib = read(symlib)
pwr_n = 0
for p, f in sheets.items():
    t = read(f)
    cache_s, cache_e = next(sch_geometry.blocks(t, r'\n\t\(lib_symbols\n'))
    cache = t[cache_s:cache_e]
    power = {}
    for s, e in sch_geometry.blocks(cache, r'\n\t\t\(symbol "'):
        b = cache[s:e]
        nm = re.match(r'\s*\(symbol "([^"]+)"', b).group(1)
        if '(power)' in b[:300]:
            power[nm] = b
    new_cache = {}
    out, last = [], 0
    for s, e in list(sch_geometry.blocks(t, r'\n\t\(symbol\n')):
        b = t[s:e]
        lid = re.search(r'\(lib_id "([^"]+)"\)', b).group(1)
        if lid not in power:
            continue
        val = re.search(r'\(property "Value" "([^"]*)"', b).group(1)
        short = lid.split(':', 1)[1]
        nshort = f'{short}_{val}'
        nlid = f'{libnick}:{nshort}'

        def variant(block, old, new):
            block = block.replace(f'(symbol "{old}"', f'(symbol "{new}"', 1)
            base_old, base_new = old.split(':')[-1], new.split(':')[-1]
            block = re.sub(r'\(symbol "' + re.escape(base_old) + r'_(\d+_\d+)"', f'(symbol "{base_new}_\\1"', block)
            return re.sub(r'(\(pin power_in \w+(?:(?!\(pin ).)*?\(name )"[^"]*"', f'\\1"{val}"', block, flags=re.S)
        if nlid not in new_cache:
            new_cache[nlid] = variant(power[lid], lid, nlid)
        if not re.search(r'\n\t\(symbol "' + re.escape(nshort) + '"\n', lib):
            lb = re.search(r'\n\t\(symbol "' + re.escape(short) + r'"\n.*?\n\t\)', lib, re.S)
            lib = lib.rstrip()[:-1].rstrip() + variant(lb.group(0), short, nshort) + '\n)\n'
        pwr_n += 1
        ref = f'#PWR{pwr_n:04d}'
        nb = b.replace(f'(lib_id "{lid}")', f'(lib_id "{nlid}")').replace('"#PWR?"', f'"{ref}"')
        out.append(t[last:s] + nb)
        last = e
    t = ''.join(out) + t[last:]
    cache_s, cache_e = next(sch_geometry.blocks(t, r'\n\t\(lib_symbols\n'))
    cache = t[cache_s:cache_e]
    cache = cache.rstrip()[:-1].rstrip() + ''.join(new_cache.values()) + '\n\t)'
    t = t[:cache_s] + cache + t[cache_e:]
    write(f, t)
write(symlib, lib)
print(f'5a. {pwr_n} power ports given per-net power symbols and annotated')

# --- 5. PWR_FLAG ----------------------------------------------------------------
std = read('/usr/share/kicad/symbols/power.kicad_sym')
flag = re.search(r'\n\t\(symbol "PWR_FLAG"\n.*?\n\t\)', std, re.S).group(0)
flag_cache = flag.replace('(symbol "PWR_FLAG"', '(symbol "power:PWR_FLAG"', 1).replace('\n\t', '\n\t\t')
root_uuid = re.search(r'\(uuid "([^"]+)"\)', read(root)).group(1)


def prop(k, v, x, y):
    return (f'\n\t\t(property "{k}" "{v}"\n\t\t\t(at {x:g} {y:g} 0)\n\t\t\t(effects\n\t\t\t\t(font'
            '\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)')


nflag = 0
flagged_nets = set()
for _ in range(6):
    todo = {}
    for p, v in erc():
        it = v['items'][0]
        if v['type'] == 'power_pin_not_driven' and p in sheets:
            net = re.search(r'\[([^,]+),', it['description']).group(1)
            todo.setdefault((p, net), (it['x'], it['y']))
    if not todo:
        break
    for (p, net), (x, y) in sorted(todo.items()):
        f = sheets[p]
        t = read(f)
        sheet_uuid = re.search(r'\(sheet\n(?:(?!\n\t\(sheet\n).)*?\(uuid "([^"]+)"\)(?:(?!\n\t\(sheet\n).)*?"Sheetfile" "'
                               + re.escape(f) + '"', read(root), re.S).group(1)
        nflag += 1
        flagged_nets.add(net)
        ref = f'#FLG{nflag:03d}'
        inst = (f'\n\t(symbol\n\t\t(lib_id "power:PWR_FLAG")\n\t\t(at {x:g} {y:g} 0)\n\t\t(unit 1)'
                '\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)'
                f'\n\t\t(uuid "{U()}")' + prop('Reference', ref, x, y - 3) + prop('Value', 'PWR_FLAG', x, y - 2.54)
                + prop('Footprint', '', x, y) + prop('Datasheet', '', x, y)
                + f'\n\t\t(pin "1"\n\t\t\t(uuid "{U()}")\n\t\t)'
                f'\n\t\t(instances\n\t\t\t(project "{name}"\n\t\t\t\t(path "/{root_uuid}/{sheet_uuid}"'
                f'\n\t\t\t\t\t(reference "{ref}")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)')
        if '(symbol "power:PWR_FLAG"' not in t:
            t = t.replace('\n\t(lib_symbols\n', '\n\t(lib_symbols' + flag_cache + '\n', 1)
        t = t.rstrip()[:-1].rstrip() + inst + '\n)\n'
        write(f, t)
print(f'5. PWR_FLAGs: {nflag} on nets {sorted(flagged_nets)}')

# --- 6. test point values, drawing frames ------------------------------------
SYM = re.compile(r'(\n\t\(symbol\n\t\t\(lib_id "([^"]+)"\)(?:.*?))(\n\t\))', re.S)
for p, f in sheets.items():
    def six(m):
        body = m.group(1)
        ref = re.search(r'\(property "Reference" "([^"]*)"', body).group(1)
        if re.fullmatch(r'TP\d+', ref):
            body = re.sub(r'\(property "Value" ""', '(property "Value" "TestPoint"', body, count=1)
        if 'Sheet-Symbol' in m.group(2):
            body = body.replace('(in_bom yes)', '(in_bom no)').replace('(on_board yes)', '(on_board no)')
        return body + m.group(3)
    write(f, SYM.sub(six, read(f)))
print('6. test point values, drawing frames off board')

# --- 7. symbols with two versions -----------------------------------------------
lib = read(symlib)


def lib_block(t, nm, indent):
    m = re.search(r'\n' + indent + r'\(symbol "' + re.escape(nm) + r'"\n.*?\n' + indent + r'\)', t, re.S)
    return m.group(0) if m else None


for _ in range(3):
    lib = read(symlib)
    mismatch = {re.search(r"Symbol '([^']+)'", v['description']).group(1)
                for p, v in erc() if v['type'] == 'lib_symbol_mismatch'}
    if not mismatch:
        break
    for p, f in sheets.items():
        t = read(f)
        cache = re.search(r'\n\t\(lib_symbols\n.*?\n\t\)\n', t, re.S).group(0)
        for full in re.findall(r'\n\t\t\(symbol "(' + re.escape(libnick) + r':[^"]+)"', cache):
            short = full.split(':', 1)[1]
            cb = lib_block(cache, full, '\t\t')
            lb = lib_block(lib, short, '\t')
            as_lib = cb.replace('\n\t\t', '\n\t').replace(f'(symbol "{full}"', f'(symbol "{short}"', 1)
            if lb is None or short not in mismatch or \
                    re.sub(r'\s+', ' ', lb).strip() == re.sub(r'\s+', ' ', as_lib).strip():
                continue
            new = f'{short}_{p.strip("/")}'
            print(f'7. {short} on {p} differs from the library: added as {new}')
            nb = as_lib.replace(f'(symbol "{short}"', f'(symbol "{new}"', 1)
            nb = re.sub(r'\(symbol "' + re.escape(short) + r'_(\d+_\d+)"', f'(symbol "{new}_\\1"', nb)
            lib = lib.rstrip()[:-1].rstrip() + nb + '\n)\n'
            newfull = f'{libnick}:{new}'
            cb2 = cb.replace(f'(symbol "{full}"', f'(symbol "{newfull}"', 1)
            cb2 = re.sub(r'\(symbol "' + re.escape(short) + r'_(\d+_\d+)"', f'(symbol "{new}_\\1"', cb2)
            t = t.replace(cb, cb2).replace(f'(lib_id "{full}")', f'(lib_id "{newfull}")')
        write(f, t)
    write(symlib, lib)

# KiCad only reports some stubs once the nets around them are fixed
run_stubs('8.')
print('done')
