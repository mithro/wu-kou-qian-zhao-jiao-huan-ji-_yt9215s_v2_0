"""Small helpers: find s-expression blocks and compute absolute symbol pin positions
in a KiCad 9 .kicad_sch file (checked against ERC-reported pin positions)."""
import re, itertools, json
def blocks(t, start_re):
    """yield (start, end) of balanced s-expr blocks matching start_re at line start"""
    for m in re.finditer(start_re, t):
        i=m.start(); depth=0; j=i
        while True:
            c=t[j]
            if c=='(':depth+=1
            elif c==')':
                depth-=1
                if depth==0: break
            elif c=='"':
                j+=1
                while t[j]!='"':
                    if t[j]=='\\': j+=1
                    j+=1
            j+=1
        yield i, j+1
def lib_pins(t):
    cache=t[t.index('\n\t(lib_symbols'):]
    cache=cache[:next(blocks(cache,r'\n\t\(lib_symbols'))[1]]
    res={}
    for s,e in blocks(cache, r'\n\t\t\(symbol "'):
        b=cache[s:e]; nm=re.match(r'\s*\(symbol "([^"]+)"',b).group(1)
        res[nm]=[(float(x),float(y),num) for x,y,num in re.findall(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+)[^)]*\).*?\(number "([^"]*)"',b,re.S)]
    return res
def xform(px,py,x,y,a,mir,variant=0):
    X,Y=px,-py
    for _ in range(int(a)//90%4): X,Y=Y,-X
    if mir=='x': Y=-Y
    if mir=='y': X=-X
    return round(x+X,3), round(y+Y,3)
def sym_pins(t):
    lp=lib_pins(t); out=[]
    for s,e in blocks(t, r'\n\t\(symbol\n'):
        b=t[s:e]
        lid=re.search(r'\(lib_id "([^"]+)"',b).group(1)
        x,y,a=map(float,re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)',b).groups())
        mm=re.search(r'\n\t\t\(mirror (\w)\)',b); mir=mm.group(1) if mm else None
        ref=re.search(r'\(property "Reference" "([^"]*)"',b).group(1)
        for px,py,num in lp.get(lid,[]):
            out.append((ref,num,)+xform(px,py,x,y,a,mir))
    return out
