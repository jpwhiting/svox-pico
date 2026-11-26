#!/usr/bin/env python3
# dt2pkb.py --- compiles a decision tree (DT) source into a DT pkb
#
# Replacement for SVOX dt2pkb.exe
#   usage: dt2pkb <dtfmt_file> <dt_file> <output_pkb>
#
# Source formats: SVOX_Pico_Lingware.pdf, chapter 3.
# Binary format: see picokdt.c (header, input map tables, output map table,
# tree node infos and the bit stream of the tree body).
#
# The original compiler's choices are reproduced so that the output is
# byte identical:
#  - the values used in subset questions of an attribute are ordered by the
#    "close order" algorithm (smaller subsets are made contiguous inside the
#    next larger subset containing them), using MSVC's unstable std::sort
#  - subsets are coded as one value, two values, range or bit mask
#  - nodes are stored breadth first, decision leaves are folded into their
#    parent node, jumps are relative bit offsets; field widths and jumps
#    are relaxed until stable
#
# Licensed under the Apache License, Version 2.0

import argparse
import os
import re
import sys

import msvcsort
import proptable
import picoscanner as sc

T_PHONE, T_GRAPH, T_POS, T_NUMERIC, T_HISTORY = 0, 1, 2, 3, 4
TYPENAMES = {'phone': T_PHONE, 'graph': T_GRAPH, 'pos': T_POS,
             'numeric': T_NUMERIC, 'history': T_HISTORY}

MT_EMPTY, MT_BYTE, MT_WORD, MT_GRAPH, MT_BYTETOVAR = 0, 1, 2, 3, 4

N_BINARY, N_CONTINUOUS, N_DISCRETE = 1, 2, 3
S_ONE, S_TWO, S_RANGE, S_MASK = 0, 1, 2, 3


class DTError(Exception):
    pass


def bkey(s):
    """std::string ordering (byte wise)"""
    return s.encode('utf-8')


def nbits(v):
    """number of bits as computed by the original tool (at least 1)"""
    n, p = 1, 2
    if v > 1:
        while p <= v:
            p *= 2
            n += 1
    return n


# ----------------------------------------------------------------------
# configuration (dtfmt) file
# ----------------------------------------------------------------------

class Attr:
    def __init__(self, num, atype, table):
        self.num = num          # 1.. or 'target'
        self.type = atype
        self.table = table      # dict symbol -> mapval or None


def load_table(path):
    t = proptable.parse_file(path)
    return {s: int(p['mapval']) for s, p in t.items() if 'mapval' in p}


def parse_dtfmt(path):
    text = sc.read_text(path)
    p = sc.Parser(sc.tokenize(text, path, range_comments=False), path)
    base = os.path.dirname(os.path.abspath(path))
    attrs = {}
    while not p.at(sc.EOF):
        p.expect(sc.KW, 'ATTR', 'keyword ATTR')
        num = p.expect(sc.STR, what='attribute number string').value
        p.expect(sc.KW, 'PROP', 'keyword PROP')
        table = None
        atype = None
        while p.at(sc.ID) and p.tok.value in ('table', 'type'):
            name = p.next().value
            p.expect(sc.PUNCT, '=', "'='")
            if name == 'table':
                rel = p.expect(sc.STR, what='table path').value.replace('\\', '/')
                table = load_table(os.path.join(base, rel))
            else:
                t = p.expect(sc.ID, what='type').value
                if t not in TYPENAMES:
                    p.error('unknown attribute type %s' % t)
                atype = TYPENAMES[t]
        if atype is None:
            p.error('type expected')
        key = 'target' if num == 'target' else int(num)
        if key in attrs:
            p.error('attribute %s defined twice' % num)
        attrs[key] = Attr(key, atype, table)
    if 'target' not in attrs:
        raise DTError('%s: the target definition is not found' % path)
    return attrs


# ----------------------------------------------------------------------
# decision tree file
# ----------------------------------------------------------------------

class Node:
    def __init__(self, num):
        self.num = num
        self.quest = None
        self.kind = None          # 'bin' 'cont' 'disc' 'dec'
        self.cut = None
        self.subsets = []         # list of value lists (source strings)
        self.yes = []
        self.no = None
        self.decision = None
        # filled later
        self.children = []        # list of ('N', node) or ('D', index)
        self.descs = []
        self.size = 0


re_field = re.compile(r'(\w+)\s*=\s*(\S+)|(\w+)')


def parse_dt(path, attrs):
    nodes = []
    header = {}
    with open(path, encoding='utf-8', errors='surrogateescape') as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.split('!', 1)[0].strip()
            if not line:
                continue
            fields = re_field.findall(line)
            if not line.startswith('node_num'):
                for k, v, w in fields:
                    if k in ('size', 'num_attributes'):
                        header[k] = int(v)
                    else:
                        raise DTError('%s(%d): unknown fields' % (path, lineno))
                continue
            n = None
            for k, v, w in fields:
                if w:
                    if w == 'is_true':
                        n.kind = 'bin'
                        continue
                    raise DTError('%s(%d): unknown field %s' % (path, lineno, w))
                if k == 'node_num':
                    n = Node(int(v))
                elif k == 'quest_num':
                    n.quest = int(v)
                elif k == 'is_greater':
                    n.kind = 'cont'
                    n.cut = int(v)
                elif k == 'subset':
                    n.kind = 'disc'
                    vals = [x for x in v.split(',') if x]
                    q = n.quest
                    a = attrs.get(q + 1) if q is not None else None
                    out = []
                    for x in vals:
                        if a is not None and a.type == T_NUMERIC:
                            out.append(x)
                        else:
                            out.append(x.replace('_EQUAL_', '='))
                    n.subsets.append(out)
                elif k == 'node_yes':
                    n.yes.append(int(v))
                elif k == 'node_no':
                    n.no = int(v)
                elif k == 'decision':
                    n.kind = 'dec'
                    n.decision = v.replace('_EQUAL_', '=')
                else:
                    raise DTError('%s(%d): unknown field %s' % (path, lineno, k))
            if n.kind is None:
                raise DTError('%s(%d): the node is not complete' % (path, lineno))
            nodes.append(n)
    return header, nodes


# ----------------------------------------------------------------------
# compiler
# ----------------------------------------------------------------------

class Compiler:
    def __init__(self, attrs, nodes):
        self.attrs = attrs
        self.allnodes = nodes
        self.nratt = len(attrs) - 1
        self.target = attrs['target']

    # value conversion (picotbread_tbrConvertIndex)
    def convert(self, attnum, value):
        a = self.attrs.get(attnum)
        if a is None:
            raise DTError('the order number %d of the vector attribute is not found' % attnum)
        t = a.type
        if t == T_GRAPH:
            return '1' if value == '_eow_' else value
        if t == T_POS and value == '0':
            return '7'
        if a.table is not None and value in a.table:
            return '%d' % a.table[value]
        if t == T_POS:
            raise DTError('the POS %s is not found in the table' % value)
        if t == T_NUMERIC:
            if value != '0' and _atoi(value) == 0:
                raise DTError('the value %s is not allowed for the numeric field' % value)
            return value
        if t == T_HISTORY:
            if value in self.decmap:
                return '%d' % self.decmap[value]
            if value == '0':
                return '30000'
            print('WARNING: the history value %s is not found in the decision values, '
                  'but artificially added to the decision!' % value)
            idx = len(self.decmap)
            self.decmap[value] = idx
            return '%d' % idx
        if t == T_PHONE:
            if value == '0':
                return '7'
            raise DTError('the phoneme value %s is not found in the table' % value)
        raise DTError('unknown attribute type')

    def build(self):
        byn = {}
        for n in self.allnodes:
            if n.num in byn:
                raise DTError('node %d defined twice' % n.num)
            byn[n.num] = n
        # decisions: sorted set of decision strings
        decs = sorted({n.decision for n in self.allnodes if n.kind == 'dec'}, key=bkey)
        self.decmap = {d: i for i, d in enumerate(decs)}

        # children; decision nodes are folded into their parents
        def child(num):
            c = byn.get(num)
            if c is None:
                raise DTError('the value of the child field is wrong (%d)' % num)
            if c.kind == 'dec':
                return ('D', self.decmap[c.decision])
            return ('N', c)

        inner = [n for n in self.allnodes if n.kind != 'dec']
        for n in inner:
            if n.kind == 'disc':
                if len(n.yes) != len(n.subsets) or n.no is None:
                    raise DTError('node %d: subsets and node_yes do not match' % n.num)
                n.children = [child(x) for x in n.yes] + [child(n.no)]
            else:
                if len(n.yes) != 1 or n.no is None:
                    raise DTError('node %d: node_yes/node_no missing' % n.num)
                n.children = [child(n.no), child(n.yes[0])]
            if n.quest is None or not 0 <= n.quest < self.nratt:
                raise DTError('node %d: invalid quest_num' % n.num)

        # input value orders (close order) per attribute
        self.orders = [self.close_order(inner, q) for q in range(self.nratt)]
        self.valindex = [{v: i for i, v in enumerate(o)} for o in self.orders]

        # subset descriptors
        for n in inner:
            n.descs = [self.descriptor(n.quest, s) for s in n.subsets]

        # breadth first order starting at the first node
        if not inner:
            raise DTError('empty tree')
        root = inner[0]
        order = [root]
        seen = {id(root)}
        i = 0
        while i < len(order):
            for kind, c in order[i].children:
                if kind == 'N':
                    if id(c) in seen:
                        raise DTError('graph instead of tree')
                    seen.add(id(c))
                    order.append(c)
            i += 1
        self.order = order
        for k, n in enumerate(order):
            n.idx = k

        # input map tables (converted values), may extend decmap (history)
        self.inmaps = []
        for q in range(self.nratt):
            # std::map<string,int> iteration: keys in string order
            m = {}
            for v in sorted(self.orders[q], key=bkey):
                m[self.convert(q + 1, v)] = self.valindex[q][v]
            self.inmaps.append(m)

    def close_order(self, inner, q):
        subs = []
        allv = set()
        for n in inner:
            if n.quest == q:
                for s in n.subsets:
                    allv.update(s)
                    subs.append(list(s))
        full = sorted(allv, key=bkey)
        if len(full) < 3:
            subs = []
        subs.append(full)
        for s in subs:
            s.sort(key=bkey)
        lt = lambda a, b: len(a) < len(b)
        msvcsort.sort(subs, lt)
        i = 0
        while i < len(subs):
            if len(subs) > 1:
                if len(subs[i]) < 3:
                    del subs[i]
                    i -= 1
                else:
                    j = i + 1
                    while j < len(subs):
                        if subs[i] == subs[j]:
                            del subs[j]
                            j -= 1
                        j += 1
            i += 1
        msvcsort.sort(subs, lt)
        sets = [set(s) for s in subs]
        for i in range(len(subs)):
            for j in range(i + 1, len(subs)):
                if sets[i] <= sets[j]:
                    sub, sup = subs[i], subs[j]
                    p = sup.index(sub[0])
                    for k in range(len(sub) - 1, 0, -1):
                        u = sup.index(sub[k])
                        del sup[u]
                        if u < p:
                            sup.insert(p, sub[k])
                            p -= 1
                        else:
                            sup.insert(p + 1, sub[k])
                    break
        return subs[-1]

    def descriptor(self, q, values):
        idx = sorted(self.valindex[q][v] for v in values)
        if len(idx) == 1:
            return (S_ONE, idx[0], 0, None)
        if len(idx) == 2:
            return (S_TWO, idx[0], idx[1], None)
        lo, hi = idx[0], idx[-1]
        if hi - lo + 1 == len(idx):
            return (S_RANGE, lo, len(idx), None)
        s = set(idx)
        mask = [1 if lo + k in s else 0 for k in range(hi - lo + 1)]
        return (S_MASK, lo, hi - lo + 1, mask)

    # ------------------------------------------------------------------
    def node_type(self, n):
        return {'bin': N_BINARY, 'cont': N_CONTINUOUS, 'disc': N_DISCRETE}[n.kind]

    def compute_widths(self):
        na = self.nratt
        vf = [0, 0]
        qf = [[0] * 5 for _ in range(na)]
        for n in self.order:
            q = n.quest
            vf[0] = max(vf[0], q)
            for kind, c in n.children:
                if kind == 'D':
                    vf[1] = max(vf[1], c)
                else:
                    qf[q][3] = max(qf[q][3], c.idx - n.idx)
            if n.kind == 'cont':
                qf[q][4] = max(qf[q][4], n.cut & 0x7fff)
            elif n.kind == 'disc':
                qf[q][0] = max(qf[q][0], len(n.children) & 0x7fff)
                for st, bp, bc, mask in n.descs:
                    qf[q][1] = max(qf[q][1], bp)
                    qf[q][2] = max(qf[q][2], bc)
        self.vf = [nbits(v) for v in vf]
        self.qf = [[nbits(v) for v in row] for row in qf]
        for n in self.order:
            n.size = self.node_size(n)
        # relax jumps
        while True:
            for n in self.order:
                q = n.quest
                n.jumps = []
                for ci, (kind, c) in enumerate(n.children):
                    if kind != 'N':
                        n.jumps.append(None)
                        continue
                    j = 0
                    for kind2, c2 in n.children[ci + 1:]:
                        j += 1 + (self.qf[q][3] if kind2 == 'N' else self.vf[1])
                    for k in range(n.idx + 1, c.idx):
                        j += self.order[k].size
                    n.jumps.append(j)
            maxj = [0] * na
            for n in self.order:
                for j in n.jumps:
                    if j is not None:
                        maxj[n.quest] = max(maxj[n.quest], j)
            changed = False
            for q in range(na):
                w = nbits(maxj[q])
                if w != self.qf[q][3]:
                    self.qf[q][3] = w
                    changed = True
            if not changed:
                break
            for n in self.order:
                n.size = self.node_size(n)
        self.totalbits = sum(n.size for n in self.order)

    def node_size(self, n):
        q = n.quest
        Q = self.qf[q]
        s = 2 + self.vf[0]
        if n.kind == 'cont':
            s += Q[4]
        elif n.kind == 'disc':
            s += Q[0]
            for st, bp, bc, mask in n.descs:
                s += 2 + Q[1]
                if st in (S_TWO, S_RANGE):
                    s += Q[2]
                elif st == S_MASK:
                    s += Q[2] + len(mask)
        for kind, c in n.children:
            s += 1 + (Q[3] if kind == 'N' else self.vf[1])
        return s

    def body(self):
        nbytes = self.totalbits // 8 + 1
        buf = bytearray(nbytes)
        pos = [0]

        def put(v, w):
            for k in range(w - 1, -1, -1):
                if (v >> k) & 1:
                    buf[pos[0] >> 3] |= 0x80 >> (pos[0] & 7)
                pos[0] += 1

        for n in self.order:
            q = n.quest
            Q = self.qf[q]
            put(self.node_type(n), 2)
            put(q, self.vf[0])
            if n.kind == 'cont':
                put(n.cut & 0x7fff, Q[4])
            elif n.kind == 'disc':
                put(len(n.children) & 0x7fff, Q[0])
                for st, bp, bc, mask in n.descs:
                    put(st, 2)
                    put(bp, Q[1])
                    if st in (S_TWO, S_RANGE):
                        put(bc, Q[2])
                    elif st == S_MASK:
                        put(bc, Q[2])
                        for b in mask:
                            put(b, 1)
            for (kind, c), j in zip(n.children, n.jumps):
                if kind == 'N':
                    put(0, 1)
                    put(j, Q[3])
                else:
                    put(1, 1)
                    put(c, self.vf[1])
        assert pos[0] == self.totalbits
        return bytes(buf)

    # ------------------------------------------------------------------
    def in_tables(self):
        out = bytearray([self.nratt & 0xff])
        for q in range(self.nratt):
            m = self.inmaps[q]
            if not m:
                out += (3).to_bytes(2, 'little') + bytes([MT_EMPTY])
                continue
            a = self.attrs[q + 1]
            if a.type in (T_HISTORY, T_NUMERIC):
                mt = MT_WORD
            elif a.type in (T_PHONE, T_POS):
                mt = MT_BYTE
            else:
                mt = MT_GRAPH
            keys = [None] * len(self.orders[q])
            for k, i in m.items():
                keys[i] = k
            keys = [k for k in keys if k is not None]
            data = bytearray()
            for k in keys:
                if mt == MT_BYTE:
                    data.append(_atoi(k) & 0xff)
                elif mt == MT_WORD:
                    data += (_atoi(k) & 0xffff).to_bytes(2, 'little')
                else:
                    data += k.encode('utf-8', 'surrogateescape')
            out += (len(data) + 5).to_bytes(2, 'little') + bytes([mt])
            out += len(m).to_bytes(2, 'little') + data
        return bytes(out)

    def target_values(self, dec):
        t = self.target
        if t.table is not None and dec in t.table:
            return [t.table[dec]]
        if t.type == T_POS:
            raise DTError('the POS %s is not found in the target table' % dec)
        if t.type == T_NUMERIC:
            if _atoi(dec) == 0 and dec != '0':
                raise DTError('the value %s is not allowed for the numeric field' % dec)
            return [_atoi(dec)]
        if t.type != T_PHONE:
            raise DTError('the type for the target attribute is not valid')
        if dec == '_epsilon_':
            return [7]
        s = dec
        for a, b in (('ACC1', "'"), ('ACC2', ','), ('_LONG', ':')):
            s = s.replace(a, b, 1)
        res = []
        for part in [x for x in s.split('-') if x]:
            if part == 'SYLL':
                part = '-'
            if t.table is None or part not in t.table:
                raise DTError('the value %s, which is the decomposition of the %s, '
                              'is not found in the table' % (part, dec))
            res.append(t.table[part])
        return res

    def out_table(self):
        vals = {}
        for d, i in sorted(self.decmap.items(), key=lambda x: bkey(x[0])):
            vals[i] = self.target_values(d)
        items = [vals[i] for i in sorted(vals)]
        mt = MT_BYTETOVAR if any(len(v) > 1 for v in items) else MT_WORD
        data = bytearray()
        if mt == MT_WORD:
            for v in items:
                data += (v[0] & 0xffff).to_bytes(2, 'little')
        else:
            flat = bytearray()
            for v in items:
                for x in v:
                    flat.append(x & 0xff)
                data += (len(flat) & 0xffff).to_bytes(2, 'little')
            data += flat
        tab = (len(data) + 5).to_bytes(2, 'little') + bytes([mt]) + \
            len(items).to_bytes(2, 'little') + data
        return bytes([1]) + tab

    def compile(self):
        self.build()
        intab = self.in_tables()
        outtab = self.out_table()
        self.compute_widths()
        body = self.body()
        tree = bytearray([2] + self.vf + [self.nratt & 0xff, 5])
        for row in self.qf:
            tree += bytes(row)
        tree += len(body).to_bytes(4, 'little') + body
        inpos = 6
        outpos = inpos + len(intab)
        treepos = outpos + len(outtab)
        hdr = inpos.to_bytes(2, 'little') + (outpos & 0xffff).to_bytes(2, 'little') + \
            (treepos & 0xffff).to_bytes(2, 'little')
        return hdr + intab + outtab + bytes(tree)


def _atoi(s):
    m = re.match(r'\s*([-+]?\d+)', s)
    return int(m.group(1)) if m else 0


def main():
    ap = argparse.ArgumentParser(description='compile Pico decision tree to pkb')
    ap.add_argument('dtfmt')
    ap.add_argument('dt')
    ap.add_argument('out')
    a = ap.parse_args()
    print('loading DT...')
    try:
        attrs = parse_dtfmt(a.dtfmt)
        header, nodes = parse_dt(a.dt, attrs)
        data = Compiler(attrs, nodes).compile()
    except (DTError, sc.ScanError) as e:
        print('ERROR: %s' % e, file=sys.stderr)
        sys.exit(1)
    with open(a.out, 'wb') as f:
        f.write(data)
    print('DT pkb is built.')


if __name__ == '__main__':
    main()
