#!/usr/bin/env python3
"""Decompile a Pico FST knowledge base (pkb) to its source.

usage: pkb2fst.py SYMTAB.utf INPUT.pkb NAME OUTPUT.utf [PHONES.utf]

Symbol ids missing from SYMTAB are named by rule (see missing_symbol) and
written with the table to OUTPUT_symtab.utf.

Binary layout (picoloadfst.py): 4 byte file header, header of varnums,
alphabet hash table (150 buckets of offsets to chained cells), transition
table (states x classes), input epsilon table, accepting state table, cells
(input symbol, offset of the next cell in the bucket, pairs of output symbol
and class) and epsilon lists.

What the pkb does not keep: the automaton name (given), comments, which
class is the default one (the most frequent class is used) and the source
order of the alphabet, which only matters inside the groups of input symbols
with equal value modulo 200 (the compiler reverses it there).

Licensed under the Apache License, Version 2.0
"""
import sys

import picoloadfst

SRC_HASH_SIZE = 200


def varnum(b, p):
    """decode a varnum at p (7 bit groups, the last one has bit 7 set)"""
    u = 0
    while True:
        c = b[p]
        p += 1
        u = (u << 7) | (c & 0x7f)
        if c & 0x80:
            break
    v = -(u + 1) // 2 if u & 1 else u // 2
    return v, p


def fixed_signed(b, p, n):
    u = int.from_bytes(b[p:p + n], 'big')
    return -(u + 1) // 2 if u & 1 else u // 2


def parse(pkb):
    base = 4
    p = base
    h = []
    for _ in range(10):
        v, p = varnum(pkb, p)
        h.append(v)
    mode, nC, nS, termClass, hsize, htoff, esize, ttoff, etoff, atoff = h
    trans = {}
    q = base + ttoff
    for s in range(1, nS + 1):
        for c in range(1, nC + 1):
            t = int.from_bytes(pkb[q:q + esize], 'big')
            q += esize
            if t:
                trans[(s, c)] = t
    cells = []                      # (insym, [(outsym, class)])
    for k in range(hsize):
        off = fixed_signed(pkb, base + htoff + 4 * k, 4)
        if off == 0:
            continue
        cp = base + htoff + off
        while True:
            sym, r = varnum(pkb, cp)
            nxt, r = varnum(pkb, r)
            pairs = []
            while True:
                o, r = varnum(pkb, r)
                if o == -1:
                    break
                c, r = varnum(pkb, r)
                pairs.append((o, c))
            cells.append((sym, pairs))
            if nxt == 0:
                break
            cp += nxt
    return {'nC': nC, 'nS': nS, 'trans': trans, 'cells': cells}


def quote(s):
    if '"' in s:
        return "'" + s + "'"
    return '"' + s + '"'


def missing_symbol(i, phones):
    """a name for a symbol id that is not in the symbol table: the phone of
    that id (ids below 256 are phone ids in the map-xsampa tables), else the
    character id - 256 (the convention of the X-SAMPA tables, '#' is the
    terminator and is written {#})"""
    if i < 256 and phones is not None:
        for s, k in phones.items():
            if k == i:
                return s
    if 256 < i < 384:
        c = chr(i - 256)
        return '{#}' if c == '#' else c
    return 'ID%d' % i


def decompile(symtab_path, pkb, name, phones_path=None):
    """source text and the symbols that had to be added to the symbol table"""
    symtab = picoloadfst.load_symtab(symtab_path)
    phones = picoloadfst.load_symtab(phones_path) if phones_path else None
    inv = {}
    for s, i in symtab.items():
        inv.setdefault(i, s)
    f = parse(pkb)
    added = []
    for i, pairs in f['cells']:
        for k in [i] + [o for o, c in pairs]:
            if k and k not in inv:
                inv[k] = missing_symbol(k, phones)
                added.append((inv[k], k))

    def sym(i):
        return '@' if i == 0 else quote(inv[i])

    def pair(i, o):
        return sym(i) if i == o else '%s/%s' % (sym(i), sym(o))

    # alphabet: per bucket (input symbol modulo 200) the pairs of its cells,
    # reversed because the compiler reverses the source order there
    buckets = [[] for _ in range(SRC_HASH_SIZE)]
    classes = {}
    for i, pairs in f['cells']:
        for o, c in pairs:
            buckets[i % SRC_HASH_SIZE].append((i, o))
            classes[(i, o)] = c
    # cells of one bucket appear in the order of their first pair; keep it
    alphabet = []
    for b in buckets:
        alphabet.extend(reversed(b))
    count = {}
    for c in classes.values():
        count[c] = count.get(c, 0) + 1
    default = max(sorted(count), key=lambda c: count[c])

    out = [':ALPHABET']
    for i, o in alphabet:
        out.append('  ' + pair(i, o))
    out.append('*')
    out.append(':AUTOMATON %s' % quote(name))
    out.append(':DEFAULTCLASS %d' % default)
    for c in sorted(count):
        if c == default:
            continue
        out.append(':CLASS %d :IS' % c)
        for i, o in alphabet:
            if classes[(i, o)] == c:
                out.append('  ' + pair(i, o))
    for s in range(1, f['nS'] + 1):
        out.append(':TRANS %d :TO %s' % (s, ' '.join(
            str(f['trans'].get((s, c), 0)) for c in range(1, f['nC'] + 1))))
    out.append('*')
    return '\n'.join(out) + '\n', added


def extend_symtab(symtab_path, added):
    """the symbol table source with the added symbols appended"""
    text = open(symtab_path, encoding='utf-8', errors='surrogateescape').read()
    if not text.endswith('\n'):
        text += '\n'
    for s, i in sorted(added, key=lambda x: x[1]):
        text += ':SYM %-20s :PROP mapval = %5d\n' % (quote(s), i)
    return text


def main():
    phones = sys.argv[5] if len(sys.argv) > 5 else None
    text, added = decompile(sys.argv[1], open(sys.argv[2], 'rb').read(), sys.argv[3], phones)
    open(sys.argv[4], 'w', encoding='utf-8', errors='surrogateescape').write(text)
    if added:
        open(sys.argv[4][:-4] + '_symtab.utf', 'w', encoding='utf-8',
             errors='surrogateescape').write(extend_symtab(sys.argv[1], added))
        print('symbols added to the symbol table: %s' % added)


if __name__ == '__main__':
    main()
