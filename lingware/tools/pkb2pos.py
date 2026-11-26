#!/usr/bin/env python3
"""Decompile a Pico part of speech table (TAB_POS pkb) to its source.

usage: pkb2pos.py TEMPLATE_pos.utf INPUT.pkb OUTPUT.utf

The pkb holds only numbers: per group (1 = primary tags, 2..8 = combinations
of that many tags) the count and offset, the primary mapvals and per
combination its mapval and the mapvals of its parts. The names of the
primary tags come from the template (same mapvals); a combination is named
by its parts joined with '^'. picoloadpos.py writes the combinations of each
size in source order: they are written in mapval order when that keeps it,
else in the order of the pkb.

Licensed under the Apache License, Version 2.0
"""
import struct
import sys

import proptable


def decode(pkb):
    hdr = [struct.unpack_from('<HH', pkb, 4 * i) for i in range(8)]
    prim = list(pkb[hdr[0][1]:hdr[0][1] + hdr[0][0]])
    comb = []                       # (size, mapval, parts) in pkb order
    for size in range(2, 9):
        n, off = hdr[size - 1]
        for k in range(n):
            e = pkb[off + k * (size + 1):off + (k + 1) * (size + 1)]
            comb.append((size, e[0], list(e[1:])))
    return prim, comb


def decompile(template, pkb):
    t = proptable.parse_file(template)
    name = {}
    for s, pr in t.items():
        if not int(pr.get('iscombined', 0)):
            name[int(pr['mapval'])] = s
    head = []
    for line in open(template, encoding='utf-8', errors='surrogateescape').read().splitlines():
        if line.startswith(':SYM'):
            break
        head.append(line)
    prim, comb = decode(pkb)
    missing = [m for m in prim if m not in name]
    if missing:
        raise ValueError('primary tags without a name in the template: %s' % missing)
    by_map = sorted(comb, key=lambda c: c[1])
    # the mapval order keeps the order inside each size?
    def per_size(lst):
        return {s: [c[1] for c in lst if c[0] == s] for s in range(2, 9)}
    order = by_map if per_size(by_map) == per_size(comb) else comb
    out = list(head)
    for m in prim:
        out.append(':SYM %-30s :PROP mapval = %-3d' % ('"%s"' % name[m], m))
    out.append('')
    out.append('! composed PoS tags')
    for size, m, parts in order:
        sym = '^'.join(name[p] for p in parts)
        out.append(':SYM %-30s :PROP mapval = %-3d,  iscombined = 1' % ('"%s"' % sym, m))
    return '\n'.join(out) + '\n'


def main():
    text = decompile(sys.argv[1], open(sys.argv[2], 'rb').read())
    open(sys.argv[3], 'w', encoding='utf-8').write(text)


if __name__ == '__main__':
    main()
