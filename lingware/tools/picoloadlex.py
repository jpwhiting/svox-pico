#!/usr/bin/env python3
# picoloadlex.py --- creates lexicon pkb (LEX_MAIN) from lexicon source file
#
# Replacement for SVOX picoloadlex.exe
#   usage: picoloadlex <phones-file> <part-of-speech-file> <lex-file> <pil-file>
#
# Lexicon source (SVOX_Pico_Lingware.pdf, chapter 6):
#   Lexicon = { Entry } .
#   Entry   = PoS Ortho ( Phono | ":G2P" ) .
#
# Binary format (see picoklex.c):
#   content     = searchindex {lexblock}1:NRBLOCKS2
#   searchindex = NRBLOCKS2 {GRAPH1 GRAPH1 GRAPH1 LEXBLOCKIND2}=NRBLOCKS2
#   lexblock    = {lexentry}1:  (fixed 512 bytes, zero padded)
#   lexentry    = LENGRAPH1 {GRAPH1}=LENGRAPH1-1
#                 LENPOSPHON1 POS1 {PHON1}=LENPOSPHON1-2
#   :G2P entry  : LENPOSPHON1 = 3, PHON = 5 (reserved value)
#
# Licensed under the Apache License, Version 2.0

import argparse
import struct
import sys

import picoscanner as sc
import proptable

LEXBLOCK_SIZE = 512
NEEDS_G2P = 5
SIE_NRGRAPHS = 3


def parse_lexicon(path, phones, pos):
    text = sc.read_text(path)
    p = sc.Parser(sc.tokenize(text, path, id_chars='^'), path)
    entries = []
    while not p.at(sc.EOF):
        t = p.next()
        if t.kind not in (sc.ID, sc.INT, sc.STR):
            p.error('part-of-speech identifier expected', t)
        tag = str(t.value)
        posid = pos.lookup(tag)
        if posid is None:
            p.error('unknown part-of-speech symbol or combination: %s' % tag, t)
        g = p.expect(sc.STR, what='grapheme string')
        graph = g.value.encode('utf-8')
        if p.accept(sc.KW, 'G2P'):
            phon = None
        else:
            ph = p.expect(sc.STR, what='phonetic string')
            phon = phones.transcribe(ph.value)
            if phon is None:
                p.error('illegal phonetic string "%s"' % ph.value, ph)
        if len(graph) + 1 > 255 or (phon is not None and len(phon) + 2 > 255):
            p.error('invalid lexicon entry (too long)', g)
        entries.append((graph, posid, phon))
    return entries


def encode_entry(graph, posid, phon):
    b = bytearray()
    b.append(len(graph) + 1)
    b += graph
    if phon is None:
        b += bytes([3, posid, NEEDS_G2P])
    else:
        b.append(len(phon) + 2)
        b.append(posid)
        b += bytes(phon)
    return bytes(b)


def _prefix(graph):
    return (graph + b'\0\0\0')[:SIE_NRGRAPHS]


def build(entries):
    """Two-pass block layout, faithful to the original picoloadlex.

    Pass 0 decides where blocks start (and writes the search index), pass 1
    writes the lexblocks.  When a new block would start in the middle of a
    group of entries sharing the same 3-byte search prefix, the whole group
    is moved to the new block. Like the original tool, the size of the moved
    group is estimated as (512 - group offset), i.e. including the unused
    tail of the old block, which is why some blocks are not filled up."""
    # sort by grapheme (byte order); homographs end up in reverse source
    # order (as produced by the original tool)
    order = sorted(range(len(entries)), key=lambda i: (entries[i][0], -i))
    entries = [entries[i] for i in order]
    datas = [encode_entry(*e) for e in entries]
    prefixes = [_prefix(e[0]) for e in entries]
    flags = [0] * len(entries)

    out = bytearray()
    st = {}

    def close(pss):
        if pss > 0 and st['used'] > 0:
            while st['used'] < LEXBLOCK_SIZE:
                out.append(0)
                st['used'] += 1
        st['count'] += 1
        st['used'] = 0

    counts = []
    for pss in (0, 1):
        st.update(count=0, used=0, prefix=b'\0\0\0', gstart=None, goff=0)
        if pss == 0:
            out += b'\0\0'
        for k in range(len(entries)):
            size = len(datas[k])
            if pss == 0:
                if st['used'] + size > LEXBLOCK_SIZE:
                    close(pss)
            elif flags[k]:
                close(pss)
            skip_entry = False
            if st['used'] == 0:
                g = st['gstart']
                if g is not None and prefixes[g] == prefixes[k] and st['goff'] > 0:
                    flags[g] = 1
                    t = st['goff']
                    st['goff'] = 0
                    st['used'] = LEXBLOCK_SIZE - t
                    if st['used'] + size > LEXBLOCK_SIZE:
                        out += st['prefix']
                        out += struct.pack('<H', st['count'] & 0xffff)
                        close(pss)
                st['prefix'] = prefixes[k] if st['count'] > 0 else b'\0\0\0'
                if pss == 0:
                    flags[k] = 1 if (st['count'] > 0 and st['used'] == 0) else 0
                    out += st['prefix']
                    out += struct.pack('<H', st['count'] & 0xffff)
                    skip_entry = True
            if pss > 0 and not skip_entry:
                out += datas[k]
            g = st['gstart']
            if g is not None and prefixes[g] == prefixes[k]:
                st['used'] += size
            else:
                st['goff'] = st['used']
                st['used'] += size
                st['gstart'] = k
        close(pss)
        counts.append(st['count'])
        print('pass #%d : %d blocks' % (pss, st['count']))
    out[0:2] = struct.pack('<H', st['count'] & 0xffff)
    return bytes(out), st['count']


def main():
    ap = argparse.ArgumentParser(description='create Pico lexicon pkb')
    ap.add_argument('phones')
    ap.add_argument('pos')
    ap.add_argument('lex')
    ap.add_argument('pil')
    a = ap.parse_args()
    try:
        phones = proptable.PhoneTable(a.phones)
        pos = proptable.PosTable(a.pos)
        entries = parse_lexicon(a.lex, phones, pos)
    except sc.ScanError as e:
        sc.die(str(e))
    data, nb = build(entries)
    with open(a.pil, 'wb') as f:
        f.write(data)
    print('PIL created; %d blocks' % nb)


if __name__ == '__main__':
    main()
