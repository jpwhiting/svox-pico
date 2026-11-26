#!/usr/bin/env python3
"""Decompile a Pico lexicon knowledge base (LEX_MAIN pkb) to its source.

usage: pkb2lex.py PHONES.utf POS.utf INPUT.pkb OUTPUT.utf [TEMPLATE.utf]

Binary layout (picoloadlex.py): search index (number of blocks, per block
the first 3 grapheme bytes and the block number), blocks of 512 bytes with
entries LENGRAPH GRAPH.. LENPOSPHON POS PHON.., zero padded. An entry with
the single phone 5 is ":G2P".

The entries are written in the order of the pkb, which is the grapheme
order the compiler sorts by; homographs are written in reverse because the
compiler puts them in reverse source order.

Licensed under the Apache License, Version 2.0
"""
import re
import struct
import sys

import proptable

LEXBLOCK_SIZE = 512
NEEDS_G2P = 5


def entries(pkb):
    nblocks, = struct.unpack_from('<H', pkb, 0)
    base = 2 + 5 * nblocks
    out = []
    for b in range(nblocks):
        p = base + b * LEXBLOCK_SIZE
        end = p + LEXBLOCK_SIZE
        while p < end and p < len(pkb) and pkb[p]:
            lg = pkb[p]
            graph = pkb[p + 1:p + lg]
            p += lg
            lp = pkb[p]
            pos = pkb[p + 1]
            phon = list(pkb[p + 2:p + lp])
            p += lp
            out.append((graph, pos, phon))
    return out


class Inverse:
    def __init__(self, phones_path, pos_path):
        self.phones = proptable.PhoneTable(phones_path)
        self.id2syms = {}
        for s, i in self.phones.sym2id.items():
            self.id2syms.setdefault(i, []).append(s)
        pos = proptable.PosTable(pos_path)
        self.pos_path = pos_path
        self.id2pos = {}
        for s, i in pos.sym2id.items():
            self.id2pos.setdefault(i, s)

    def phon(self, ids):
        """a phonetic string that transcribes back to ids"""
        # first choice: the first symbol of each id; check, else search
        s = ''.join(self.id2syms[i][0] for i in ids)
        if self.phones.transcribe(s) == ids:
            return s
        return self._search(ids, 0, '')

    def _search(self, ids, k, acc):
        if k == len(ids):
            return acc if self.phones.transcribe(acc) == ids else None
        for sym in self.id2syms[ids[k]]:
            r = self._search(ids, k + 1, acc + sym)
            if r is not None:
                return r
        return None


def quote(s):
    """a string token: single quotes when it contains a double quote"""
    if '"' in s:
        if "'" in s:
            raise ValueError('both quotes in %r' % s)
        return "'" + s + "'"
    return '"' + s + '"'


re_entry = re.compile(r'''^\s*(\S+)\s+("[^"]*"|'[^']*')\s+(:G2P|"[^"]*"|'[^']*')\s*$''')


def parse_entry(m, pos, inv):
    """(graph bytes, pos id, phone ids) of a matched entry line, or None"""
    posid = pos.lookup(m.group(1))
    graph = m.group(2)[1:-1].encode('utf-8', 'surrogateescape')
    if m.group(3) == ':G2P':
        phon = (NEEDS_G2P,)
    else:
        ph = inv.phones.transcribe(m.group(3)[1:-1])
        phon = tuple(ph) if ph is not None else None
    if posid is None or phon is None:
        return None
    return (graph, posid, phon)


def keep_order(inv, ents, template):
    """the lines of the template source with the entries that are still in
    the lexicon, removed ones dropped; None if the compiler would not get
    the entry order of the pkb from it. Tried in turn: new entries appended;
    the entries of the grapheme strings whose entries changed together where
    the first of them was, in the order the compiler needs (it reverses the
    source order of homographs); the same for all grapheme strings"""
    for mode in ('append', 'changed', 'all'):
        text = _keep_order(inv, ents, template, mode)
        if text is not None:
            return text
    return None


def _keep_order(inv, ents, template, mode):
    pos = proptable.PosTable(inv.pos_path)
    text = open(template, encoding='utf-8', errors='surrogateescape', newline='').read()
    lines = text.split('\n')
    eol = '\r' if sum(l.endswith('\r') for l in lines) > len(lines) // 2 else ''
    key = lambda e: (e[0], e[1], tuple(e[2]))
    groups = {}                     # grapheme -> entries in pkb order
    for e in ents:
        groups.setdefault(e[0], []).append(e)
    old = {}                        # entry key -> template lines
    parsed = []
    for line in lines:
        m = re_entry.match(line.rstrip('\r'))
        k = parse_entry(m, pos, inv) if m else None
        if k is not None:
            old.setdefault(k, []).append(line)
        parsed.append((line, k))

    # grapheme strings whose entries are not the same as in the template
    tmpl_groups = {}
    for line, k in parsed:
        if k is not None:
            tmpl_groups.setdefault(k[0], []).append(k)
    changed = {g for g in set(groups) | set(tmpl_groups)
               if sorted(map(key, groups.get(g, []))) != sorted(tmpl_groups.get(g, []))}
    regroup = (set() if mode == 'append' else changed if mode == 'changed' else set(groups))
    want = {}
    for e in ents:
        want[key(e)] = want.get(key(e), 0) + 1

    def group_lines(graph):
        out = []
        for e in reversed(groups[graph]):
            olds = old.get(key(e))
            if olds:
                out.append(olds.pop(0))
                want[key(e)] -= 1
            else:
                out.append(format_entry(inv, *e) + eol)
                want[key(e)] -= 1
        return out

    out, done = [], set()
    for line, k in parsed:
        if k is None:
            if not re_entry.match(line.rstrip('\r')):
                out.append(line)    # comments, empty lines
            continue
        g = k[0]
        if g in regroup:
            if g in groups and g not in done:
                done.add(g)
                out.extend(group_lines(g))
        elif want.get(k, 0) > 0:
            want[k] -= 1
            out.append(line)        # still in the lexicon, kept in place
    while out and out[-1] in ('', '\r'):
        out.pop()
    for e in ents:
        if e[0] in regroup:
            if e[0] not in done:
                done.add(e[0])
                out.extend(group_lines(e[0]))
        elif want.get(key(e), 0) > 0:
            want[key(e)] -= 1
            out.append(format_entry(inv, *e) + eol)
    # check: the compiler sorts by grapheme, homographs in reverse source
    # order; the whole entries must come out in the order of the pkb
    order = []
    for line in out:
        m = re_entry.match(line.rstrip('\r'))
        if m:
            k = parse_entry(m, pos, inv)
            if k is None:
                return None
            order.append(k)
    srt = sorted(range(len(order)), key=lambda i: (order[i][0], -i))
    if [order[i] for i in srt] != [key(e) for e in ents]:
        return None
    return '\n'.join(out) + '\n'


def format_entry(inv, graph, pos, phon):
    g = graph.decode('utf-8', 'surrogateescape')
    if phon == [NEEDS_G2P]:
        return '%s %s :G2P' % (inv.id2pos[pos], quote(g))
    ph = inv.phon(phon)
    if ph is None:
        raise ValueError('no phonetic string for %r' % phon)
    return '%s %s %s' % (inv.id2pos[pos], quote(g), quote(ph))


def decompile(phones_path, pos_path, pkb, template=None):
    """the lexicon source; with a template (the source of another version)
    its order, notation and comments are kept where possible"""
    inv = Inverse(phones_path, pos_path)
    ents = entries(pkb)
    if template is not None:
        text = keep_order(inv, ents, template)
        if text is not None:
            return text
    lines = []
    # homographs: reverse their order (the compiler reverses them)
    i = 0
    while i < len(ents):
        j = i
        while j < len(ents) and ents[j][0] == ents[i][0]:
            j += 1
        for graph, pos, phon in reversed(ents[i:j]):
            lines.append(format_entry(inv, graph, pos, phon))
        i = j
    return '\n'.join(lines) + '\n'


def main():
    template = sys.argv[5] if len(sys.argv) > 5 else None
    text = decompile(sys.argv[1], sys.argv[2], open(sys.argv[3], 'rb').read(), template)
    open(sys.argv[4], 'w', encoding='utf-8', errors='surrogateescape', newline='').write(text)


if __name__ == '__main__':
    main()
