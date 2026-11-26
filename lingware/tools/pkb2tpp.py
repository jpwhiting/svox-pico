#!/usr/bin/env python3
"""Decompile a Pico text preprocessing network (TPP_MAIN pkb) to the
tpp_net source that picoloadpreproc.py compiles.

usage: pkb2tpp.py TEMPLATE_tpp_net.utf INPUT.pkb OUTPUT.utf

The pkb is a header of 8 uint32 (network, size of the strings in bytes,
then the numbers of lexcats, attrvals, outitems, tokens, productions,
contexts) followed by these tables; the source lists the same tables, so
everything is recovered. The comment header and the line ends (CRLF) are
taken from the template.

Licensed under the Apache License, Version 2.0
"""
import struct
import sys

OUTTYPES = ['STR', 'VAR', 'ITEM', 'SPELL', 'ROMAN', 'VAL', 'LEFT', 'RIGHT', 'RLZ',
            'IGNORE', 'PITCH', 'SPEED', 'VOLUME', 'VOICE', 'CONTEXT', 'SVOXPA', 'SAMPA',
            'PLAY', 'USESIG', 'GENFILE', 'AUDIOEDIT', 'PARA', 'SENT', 'BREAK', 'MARK',
            'CONCAT']
WP = ['TSEOut', 'TSEMin', 'TSEMax', 'TSELen', 'TSEVal', 'TSEStr', 'TSEHead', 'TSEMid',
      'TSETail', 'TSEProd', 'TSEProdExt', 'TSEVar', 'TSELex', 'TSECost', 'TSEID',
      'TSEDummy1', 'TSEDummy2', 'TSEDummy3']
NP = ['TSEBegin', 'TSEEnd', 'TSESpace', 'TSEDigit', 'TSELetter', 'TSEChar', 'TSESeq',
      'TSECmpr', 'TSENLZ', 'TSERoman', 'TSECI', 'TSECIS', 'TSEAUC', 'TSEALC', 'TSESUC',
      'TSEAccept', 'TSENext', 'TSEAltL', 'TSEAltR']
SECTIONS = ['NETWORK', 'STRINGS', 'LEXCATS', 'ATTRVALS', 'OUTITEMS', 'TOKENS',
            'PRODUCTIONS', 'CONTEXTS']


def signed(v, nbytes):
    """inverse of valBytes of picoloadpreproc.py"""
    return v - (1 << (8 * nbytes - 1))


def flags(v, names):
    return [n for k, n in enumerate(names) if v >> k & 1]


def quote(s):
    if '"' in s:
        if "'" in s:
            raise ValueError('both quotes in string %r' % s)
        return "'" + s + "'"
    return '"' + s + '"'


def decompile(template, pkb):
    tmpl = open(template, 'rb').read().decode('utf-8', 'surrogateescape')
    nl = '\r\n' if '\r\n' in tmpl else '\n'
    header = []
    for line in tmpl.splitlines():
        if line.startswith('!') or not line.strip():
            header.append(line)
        else:
            break
    while header and not header[-1].strip():
        header.pop()
    n = struct.unpack_from('<8I', pkb, 0)
    p = 32
    out = list(header) + ['NETWORK %d' % n[0], '']

    def section(i, lines):
        out.append('%s %d' % (SECTIONS[i], n[i]))
        out.extend(lines)
        out.extend(['.', ''])

    # strings: n[1] bytes of zero terminated strings
    raw = pkb[p:p + n[1]]
    p += n[1]
    lines, off = [], 0
    for s in raw.split(b'\0')[:-1]:
        lines.append('%d %s' % (off, quote(s.decode('utf-8', 'surrogateescape'))))
        off += len(s) + 1
    assert off == n[1]
    section(1, lines)
    lines = []
    for k in range(n[2]):
        v, = struct.unpack_from('<H', pkb, p)
        p += 2
        lines.append('%d %d' % (k, signed(v, 2)))
    section(2, lines)
    lines = []
    for k in range(n[3]):
        v, = struct.unpack_from('<I', pkb, p)
        p += 4
        lines.append('%d %d' % (k, signed(v, 4)))
    section(3, lines)
    lines = []
    for k in range(n[4]):
        nxt, typ, arg = struct.unpack_from('<HBI', pkb, p)
        p += 7
        if typ in (1, 5):               # VAR and VAL are signed
            arg = signed(arg, 4)
        lines.append('%d %d %s %d' % (k, nxt, OUTTYPES[typ], arg))
    section(4, lines)
    lines = []
    for k in range(n[5]):
        wp, np_, nxt, left, right, attr = struct.unpack_from('<IIHHHH', pkb, p)
        p += 16
        lines.append('%d {%s} %d %d %d %d' % (k, ','.join(flags(wp, WP) + flags(np_, NP)),
                                              nxt, left, right, attr))
    section(5, lines)
    lines = []
    for k in range(n[6]):
        cost, name, a, e = struct.unpack_from('<IIHH', pkb, p)
        p += 12
        lines.append('%d %d %d %d %d' % (k, signed(cost, 4), name, a, e))
    section(6, lines)
    lines = []
    for k in range(n[7]):
        name, net, prod = struct.unpack_from('<III', pkb, p)
        p += 12
        lines.append('%d %d %d %d' % (k, name, net, prod))
    section(7, lines)
    if p != len(pkb):
        raise ValueError('%d bytes left at the end' % (len(pkb) - p))
    return nl.join(out) + nl


def main():
    text = decompile(sys.argv[1], open(sys.argv[2], 'rb').read())
    open(sys.argv[3], 'wb').write(text.encode('utf-8', 'surrogateescape'))


if __name__ == '__main__':
    main()
