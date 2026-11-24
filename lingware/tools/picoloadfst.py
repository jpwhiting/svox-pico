#!/usr/bin/env python3
# picoloadfst.py --- compiles FST source into FST pkb
#
# Replacement for SVOX picoloadfst.exe
#   usage: picoloadfst <inFSTFile> <inSymTabFile> <outStreamFile>
#
# Source format: SVOX_Pico_Lingware.pdf, chapter 2
#   FST = ":ALPHABET" {Pair} "*" ":AUTOMATON" Name
#         ":DEFAULTCLASS" Number {":CLASS" Number ":IS" {Pair}}
#         {":TRANS" State ":TO" {State}} "*" .
#   Pair = Symbol ["/" Symbol] ;  Symbol = String | "@" (epsilon)
#
# Symbol table: property table (:SYM "x" :PROP mapval = n), symbol '#' is
# the terminator symbol.
#
# Binary layout (read by picokfst.c), after a 4 byte file header:
#   header      : varnums  transductionMode nrClasses nrStates termClass
#                 alphaHashTabSize alphaHashTabOffs transTabEntrySize
#                 transTabOffs inEpsStateTabOffs accStateTabOffs
#   alpha hash  : alphaHashTabSize x 4 byte fixed signed offsets to cells
#   trans table : nrStates*nrClasses fixed unsigned (entry size 1..4 bytes)
#   in-eps tab  : nrStates x 4 byte fixed signed offsets to eps lists
#   acc table   : nrStates x 1 byte
#   cells       : per input symbol: insym nextSameHashOffs {outsym class} -1
#   eps lists   : per state: {outsym endstate} -1
#
# Numbers in "varnum" format are zig-zag encoded 7-bit groups, last byte
# has the high bit set.  The node order, hashing and offset relaxation
# replicate the original tool exactly so that the output is byte identical.
#
# Licensed under the Apache License, Version 2.0

import argparse
import sys

import picoscanner as sc
import proptable

TERMINATOR = '#'
ALPHA_HASH_SIZE = 150     # hash table size of the generated stream
SRC_HASH_SIZE = 200       # internal hash of the original tool (affects order
BIG = 1000000000          # initial offset value before relaxation


def zigzag(v):
    return -2 * v - 1 if v < 0 else 2 * v


def varnum(v):
    u = zigzag(v)
    out = [(u & 0x7f) | 0x80]
    u >>= 7
    while u:
        out.append(u & 0x7f)
        u >>= 7
    return bytes(reversed(out))


def fixed_signed(v, n):
    u = zigzag(v)
    if u >> (8 * n):
        raise ValueError('number too large in signedNumToFixedBytes')
    return u.to_bytes(n, 'big')


def fixed_unsigned(v, n):
    if v < 0 or v >> (8 * n):
        raise ValueError('number out of range in unsignedNumToFixedBytes')
    return v.to_bytes(n, 'big')


class FST:
    def __init__(self):
        self.buckets = [[] for _ in range(SRC_HASH_SIZE)]   # newest first
        self.pairclass = {}
        self.trans = {}         # (state, class) -> target
        self.nrStates = 0
        self.nrClasses = 0
        self.termId = None

    def add_pair(self, i, o):
        if (i, o) in self.pairclass:
            raise sc.ScanError('symbol pair %d/%d specified more than once' % (i, o))
        self.pairclass[(i, o)] = 0
        self.buckets[i % SRC_HASH_SIZE].insert(0, (i, o))

    def set_class(self, i, o, c):
        if not 1 <= c <= 200:
            raise sc.ScanError('error setting pair class %d' % c)
        if (i, o) not in self.pairclass:
            raise sc.ScanError('symbol pair %d/%d not specified in alphabet' % (i, o))
        self.pairclass[(i, o)] = c
        self.nrClasses = max(self.nrClasses, c)

    def set_default_class(self, c):
        if not 1 <= c <= 200:
            raise sc.ScanError('error setting default class %d' % c)
        for k, v in self.pairclass.items():
            if v < 1:
                self.pairclass[k] = c
        self.nrClasses = max(self.nrClasses, c)

    def set_trans(self, s, c, t):
        if not (1 <= s <= 5000 and 1 <= c <= 200 and 0 <= t <= 5000):
            raise sc.ScanError('error in setting fst transition %d -> %d with class %d'
                               % (s, t, c))
        self.trans[(s, c)] = t
        self.nrStates = max(self.nrStates, s)
        self.nrClasses = max(self.nrClasses, c)

    def pairs_in_order(self):
        for b in self.buckets:
            for p in b:
                yield p


def parse_fst(path, symtab):
    text = sc.read_text(path)
    p = sc.Parser(sc.tokenize(text, path), path)
    fst = FST()
    if TERMINATOR not in symtab:
        raise sc.ScanError('no id found for terminator symbol')
    fst.termId = symtab[TERMINATOR]

    def symbol():
        if p.accept(sc.PUNCT, '@'):
            return 0
        t = p.expect(sc.STR, what='string')
        if t.value not in symtab:
            p.error("illegal symbol '%s'" % t.value, t)
        return symtab[t.value]

    def is_symbol_start():
        return p.at(sc.STR) or p.at(sc.PUNCT, '@')

    def pair():
        i = symbol()
        o = i
        if p.accept(sc.PUNCT, '/'):
            o = symbol()
        return i, o

    p.expect(sc.KW, 'ALPHABET', 'keyword ALPHABET')
    while is_symbol_start():
        i, o = pair()
        fst.add_pair(i, o)
    p.expect(sc.PUNCT, '*', "operator '*'")
    p.expect(sc.KW, 'AUTOMATON', 'keyword AUTOMATON')
    p.expect(sc.STR, what='string')
    defclass = 0
    while True:
        if p.accept(sc.KW, 'DEFAULTCLASS'):
            defclass = p.expect(sc.INT, what='integer number').value
        elif p.accept(sc.KW, 'CLASS'):
            c = p.expect(sc.INT, what='integer number').value
            p.expect(sc.KW, 'IS', 'keyword IS')
            while is_symbol_start():
                i, o = pair()
                fst.set_class(i, o, c)
        else:
            fst.set_default_class(defclass)
            break
    state = 0
    ntrans = None
    while p.accept(sc.KW, 'TRANS'):
        state += 1
        s = p.expect(sc.INT, what='integer number')
        if s.value != state:
            p.error("wrong 'from' state number", s)
        p.expect(sc.KW, 'TO', 'keyword TO')
        n = 0
        while p.at(sc.INT):
            n += 1
            fst.set_trans(state, n, p.next().value)
        if ntrans is None:
            ntrans = n
        elif n != ntrans:
            p.error('wrong number of transitions')
    p.expect(sc.PUNCT, '*', "operator '*'")
    if not p.at(sc.EOF):
        p.error('end of file expected')
    return fst


class Node:
    __slots__ = ('kind', 'pos', 'data')

    def __init__(self, kind, **kw):
        self.kind = kind
        self.pos = 0
        self.data = kw


def build_stream(fst):
    termClass = fst.pairclass.get((fst.termId, fst.termId), 0)
    if termClass < 1:
        raise sc.ScanError('no terminator pair found in original FST')
    nS, nC = fst.nrStates, fst.nrClasses
    if nS < 0x100:
        esize = 1
    elif nS < 0x10000:
        esize = 2
    elif nS < 0x1000000:
        esize = 3
    else:
        esize = 4

    # input symbol cells (hash buckets with cells appended at the tail)
    cellbuckets = [[] for _ in range(ALPHA_HASH_SIZE)]
    cells = {}
    for (i, o) in fst.pairs_in_order():
        cell = cells.get(i)
        if cell is None:
            cell = Node('cell', sym=i, nxt=None, offs=BIG, pairs=[])
            cells[i] = cell
            cellbuckets[i % ALPHA_HASH_SIZE].append(cell)
        cell.data['pairs'].append((o, fst.pairclass[(i, o)]))
    for b in cellbuckets:
        for a, c in zip(b, b[1:]):
            a.data['nxt'] = c

    # input epsilon transitions per state
    epslists = [[] for _ in range(nS)]
    for (i, o) in fst.pairs_in_order():
        if i == 0:
            c = fst.pairclass[(i, o)]
            for s in range(1, nS + 1):
                t = fst.trans.get((s, c), 0)
                if t > 0:
                    epslists[s - 1].append((o, t))

    hdr = Node('hdr', offs=[BIG, BIG, BIG, BIG])
    htab = Node('htab')
    ttab = Node('ttab')
    etab = Node('etab')
    atab = Node('atab')
    epsnodes = [Node('eps', lst=l) if l else None for l in epslists]

    order = [hdr, htab, ttab, etab, atab]
    for b in cellbuckets:
        order.extend(b)
    order.extend(n for n in epsnodes if n is not None)

    transbytes = bytearray()
    for s in range(1, nS + 1):
        for c in range(1, nC + 1):
            transbytes += fixed_unsigned(fst.trans.get((s, c), 0), esize)
    accbytes = bytes(1 if fst.trans.get((s, termClass), 0) == 1 else 0
                     for s in range(1, nS + 1))

    def emit(n, final):
        k = n.kind
        if k == 'hdr':
            o = n.data['offs']
            return b''.join(varnum(v) for v in
                            (0, nC, nS, termClass, ALPHA_HASH_SIZE, o[0], esize,
                             o[1], o[2], o[3]))
        if k == 'htab':
            out = bytearray()
            for b in cellbuckets:
                v = (b[0].pos - htab.pos) if (final and b) else 0
                out += fixed_signed(v, 4)
            return bytes(out)
        if k == 'ttab':
            return bytes(transbytes)
        if k == 'etab':
            out = bytearray()
            for en in epsnodes:
                v = (en.pos - etab.pos) if (final and en is not None) else 0
                out += fixed_signed(v, 4)
            return bytes(out)
        if k == 'atab':
            return accbytes
        if k == 'cell':
            out = bytearray(varnum(n.data['sym']) + varnum(n.data['offs']))
            for o, c in n.data['pairs']:
                out += varnum(o) + varnum(c)
            out += varnum(-1)
            return bytes(out)
        if k == 'eps':
            out = bytearray()
            for o, t in n.data['lst']:
                out += varnum(o) + varnum(t)
            out += varnum(-1)
            return bytes(out)
        raise AssertionError(k)

    def layout():
        changed = False
        pos = 0
        for n in order:
            if n.pos != pos:
                changed = True
            n.pos = pos
            pos += len(emit(n, False))
        return changed

    def relocate():
        hdr.data['offs'] = [htab.pos - hdr.pos, ttab.pos - hdr.pos,
                            etab.pos - hdr.pos, atab.pos - hdr.pos]
        for b in cellbuckets:
            for c in b:
                nx = c.data['nxt']
                c.data['offs'] = 0 if nx is None else nx.pos - c.pos

    layout()
    while True:
        relocate()
        if not layout():
            break

    out = bytearray(b'xxxx')
    for n in order:
        out += emit(n, True)
    return bytes(out)


def load_symtab(path):
    t = proptable.parse_file(path)
    return {s: int(pr['mapval']) for s, pr in t.items() if 'mapval' in pr}


def main():
    ap = argparse.ArgumentParser(description='compile Pico FST source to pkb')
    ap.add_argument('fst')
    ap.add_argument('symtab')
    ap.add_argument('out')
    a = ap.parse_args()
    try:
        symtab = load_symtab(a.symtab)
        fst = parse_fst(a.fst, symtab)
        data = build_stream(fst)
    except (sc.ScanError, ValueError) as e:
        sc.die('*** fst error: %s' % e)
    with open(a.out, 'wb') as f:
        f.write(data)


if __name__ == '__main__':
    main()
