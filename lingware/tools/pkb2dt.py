#!/usr/bin/env python3
"""Decompile a Pico decision tree knowledge base (pkb) back to a source
that dt2pkb.py compiles to the identical pkb.

usage: pkb2dt.py DTFMT INPUT.pkb OUTPUT.utf

Binary layout (dt2pkb.py, picokdt.c): header (offsets of the input map
tables, the output map table and the tree), input map tables (per
attribute the values used in questions, in the order of their indices),
output map table (decision values), tree: field widths and a bit stream of
the nodes in breadth first order; decision leaves are folded into their
parents, other children are relative bit jumps.

The source cannot carry what the compiler drops: node numbers (inner nodes
are numbered breadth first, then one leaf node per decision), the order of
the values inside a subset (written in index order) and comments.

dt2pkb orders the values of an attribute by the file order of the nodes
asking about it ("close order"), which the pkb does not keep either. So a
decompiled tree compiles to the same tree (same questions, value sets and
decisions, hence the same speech), but its pkb may differ in the order of
the values in the input map tables. The text analysis trees of the SVOX
lingware come out byte identical, most signal generation trees do not.

Licensed under the Apache License, Version 2.0
"""
import sys

import dt2pkb

MT_EMPTY, MT_BYTE, MT_WORD, MT_GRAPH, MT_BYTETOVAR = 0, 1, 2, 3, 4
N_BINARY, N_CONTINUOUS, N_DISCRETE = 1, 2, 3
S_ONE, S_TWO, S_RANGE, S_MASK = 0, 1, 2, 3


def u16(b, p):
    return b[p] | b[p + 1] << 8


class Bits:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def get(self, w):
        v = 0
        for _ in range(w):
            v = v << 1 | ((self.data[self.pos >> 3] >> (7 - (self.pos & 7))) & 1)
            self.pos += 1
        return v


def read_map(b, p):
    """one map table at p: (type, list of entries in index order), end"""
    ln, mt = u16(b, p), b[p + 2]
    if mt == MT_EMPTY:
        return mt, [], p + ln
    n = u16(b, p + 3)
    d = b[p + 5:p + ln]
    if mt == MT_BYTE:
        vals = list(d)
    elif mt == MT_WORD:
        vals = [u16(d, 2 * i) for i in range(n)]
    elif mt == MT_GRAPH:
        vals = split_graphs(bytes(d), n)
    elif mt == MT_BYTETOVAR:
        ends = [u16(d, 2 * i) for i in range(n)]
        flat = d[2 * n:]
        vals, s = [], 0
        for e in ends:
            vals.append(list(flat[s:e]))
            s = e
    else:
        raise ValueError('unknown map table type %d' % mt)
    return mt, vals, p + ln


def split_graphs(d, n):
    """the graphs are stored as concatenated UTF-8 strings: one character each"""
    s = d.decode('utf-8', 'surrogateescape')
    if len(s) != n:
        raise ValueError('graph table: %d characters for %d entries' % (len(s), n))
    return list(s)


def decompile(attrs, pkb):
    inpos, outpos, treepos = u16(pkb, 0), u16(pkb, 2), u16(pkb, 4)
    nratt = pkb[inpos]
    p = inpos + 1
    inmaps = []
    for _ in range(nratt):
        mt, vals, p = read_map(pkb, p)
        inmaps.append((mt, vals))
    assert p == outpos
    assert pkb[outpos] == 1
    omt, outvals, p = read_map(pkb, outpos + 1)
    assert p == treepos

    t = pkb[treepos:]
    assert t[0] == 2
    vf = [t[1], t[2]]
    assert t[3] == nratt and t[4] == 5
    qf = [list(t[5 + 5 * q:10 + 5 * q]) for q in range(nratt)]
    p = 5 + 5 * nratt
    blen = int.from_bytes(t[p:p + 4], 'little')
    bits = Bits(t[p + 4:p + 4 + blen])

    # inverse conversion of the decisions and the input values
    # (dt2pkb.Compiler.target_values and .convert)
    T = dt2pkb
    tgt = attrs['target']

    def inv_table(a):
        inv = {}
        for s, m in (a.table or {}).items():
            inv.setdefault(m, s)
        return inv

    tinv = inv_table(tgt)

    def phone_seq(vals):
        if vals == [7] and 7 not in tinv:
            return '_epsilon_'
        parts = []
        for m in vals:
            s = tinv[m]
            parts.append('SYLL' if s == '-' else s)
        s = '-'.join(parts)
        for a, b in (('ACC1', "'"), ('ACC2', ','), ('_LONG', ':')):
            if b in s:
                s = s.replace(b, a, 1)
        return s

    def decision(i):
        v = outvals[i]
        if omt == MT_BYTETOVAR:
            return phone_seq(v)
        if tgt.table is not None and v in tinv:
            return tinv[v]
        if tgt.type == T.T_NUMERIC:
            return str(v)
        if tgt.type == T.T_PHONE:
            return phone_seq([v])
        raise ValueError('decision value %d not in the target table' % v)

    decisions = [decision(i) for i in range(len(outvals))]
    # (checked below: the decisions of the leaves are numbered in string
    # order; history values that are no decision are appended after them)
    ainv = {q: inv_table(attrs[q + 1]) for q in range(nratt)}

    def in_value(q, v):
        a = attrs[q + 1]
        if a.type == T.T_NUMERIC:
            return str(v)
        if a.type == T.T_GRAPH:
            return '_eow_' if v == '1' else v
        if a.type == T.T_HISTORY:
            return '0' if v == 30000 else decisions[v]
        if a.type in (T.T_POS, T.T_PHONE):
            if v == 7:
                return '0'
            return ainv[q][v]
        raise ValueError('attribute type %d' % a.type)

    # nodes in stream order; children are bit positions or decisions
    # (the stream is padded with 1 to 8 zero bits, and there is no node
    # type 0)
    nodes = {}
    order = []
    while bits.pos + 2 <= 8 * blen:
        start = bits.pos
        ntype = bits.get(2)
        if ntype == 0:
            break
        q = bits.get(vf[0])
        Q = qf[q]
        n = {'start': start, 'quest': q, 'type': ntype, 'subsets': []}
        if ntype == N_CONTINUOUS:
            n['cut'] = bits.get(Q[4])
            nch = 2
        elif ntype == N_DISCRETE:
            nch = bits.get(Q[0])
            for _ in range(nch - 1):
                st, bp = bits.get(2), bits.get(Q[1])
                if st == S_ONE:
                    idx = [bp]
                elif st == S_TWO:
                    idx = [bp, bits.get(Q[2])]
                elif st == S_RANGE:
                    idx = list(range(bp, bp + bits.get(Q[2])))
                else:
                    ln = bits.get(Q[2])
                    idx = [bp + k for k in range(ln) if bits.get(1)]
                n['subsets'].append(idx)
        else:
            nch = 2
        n['children'] = []
        for _ in range(nch):
            if bits.get(1):
                n['children'].append(('D', bits.get(vf[1])))
            else:
                j = bits.get(Q[3])
                n['children'].append(('J', j, bits.pos))
        nodes[start] = n
        order.append(n)

    used = sorted({c[1] for n in order for c in n['children'] if c[0] == 'D'})
    if used != list(range(len(used))) or \
            sorted(decisions[:len(used)], key=T.bkey) != decisions[:len(used)]:
        raise ValueError('the decisions do not sort like their indices')

    # resolve jumps, number the inner nodes breadth first
    for k, n in enumerate(order):
        n['num'] = k + 1
    leaves = []
    for n in order:
        ch = []
        for c in n['children']:
            if c[0] == 'D':
                leaves.append(decisions[c[1]])
                ch.append(len(order) + len(leaves))
            else:
                tgt = nodes.get(c[2] + c[1])
                if tgt is None:
                    raise ValueError('jump to bit %d is not a node' % (c[2] + c[1]))
                ch.append(tgt['num'])
        n['childnums'] = ch

    def src_value(q, v):
        if attrs[q + 1].type == T.T_NUMERIC:
            return v
        if ',' in v:
            raise ValueError('a comma in the subset value %r' % v)
        return v.replace('=', '_EQUAL_')

    out = ['size = %d' % (len(order) + len(leaves)), 'num_attributes = %d' % nratt]
    for n in order:
        q, line = n['quest'], 'node_num = %d quest_num = %d' % (n['num'], n['quest'])
        ch = n['childnums']
        if n['type'] == N_DISCRETE:
            vals = inmaps[q][1]
            for idx, c in zip(n['subsets'], ch[:-1]):
                line += ' subset = %s node_yes = %d' % (
                    ','.join(src_value(q, in_value(q, vals[i])) for i in idx), c)
            line += ' node_no = %d' % ch[-1]
        elif n['type'] == N_CONTINUOUS:
            line += ' is_greater = %d node_yes = %d node_no = %d' % (n['cut'], ch[1], ch[0])
        else:
            line += ' is_true node_yes = %d node_no = %d' % (ch[1], ch[0])
        out.append(line)
    for k, d in enumerate(leaves):
        out.append('node_num = %d decision = %s' % (len(order) + k + 1, d.replace('=', '_EQUAL_')))
    return '\n'.join(out) + '\n'


def main():
    attrs = dt2pkb.parse_dtfmt(sys.argv[1])
    text = decompile(attrs, open(sys.argv[2], 'rb').read())
    open(sys.argv[3], 'w', encoding='utf-8', errors='surrogateescape').write(text)


if __name__ == '__main__':
    main()
