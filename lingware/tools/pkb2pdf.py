#!/usr/bin/env python3
"""Decompile a Pico PDF knowledge base (pkb) back to its .utf source.

usage: pkb2pdf.py TEMPLATE.utf INPUT.pkb OUTPUT.utf

The PDF source is a sequence of specs (key = count, type) each followed by
its values; the pkb is those values as little endian integers. The specs and
comments are taken from a template source of the same kind (e.g. the 1.0.0.3
source of the voice); the counts that depend on the data are recomputed:

  numframesperstate   numstates values
  phonquant           phonquantlen values
  statequant          statequantlen values
  meanpowum, ivarpow  3 * ceporder values
  content             the rest of the pkb
  phase pdf           index has numvectors values, then per vector a pair
                      n_comps (1 value) and phase (n_comps values); the
                      pairs are generated from the data

pdf2pkb.py compiles the output back to the identical pkb.

Licensed under the Apache License, Version 2.0
"""
import re
import sys

TYPES = {'uint8': 1, 'uint16': 2, 'uint32': 4}
re_spec = re.compile(r'^(\s*)(\w+)(\s*=\s*)(\d+)(\s*,\s*)(\w+)(.*)$')
re_values = re.compile(r'^[-+]?\d+(\s+[-+]?\d+)*$')

DEPENDS = {'numframesperstate': lambda v: v['numstates'][0],
           'phonquant': lambda v: v['phonquantlen'][0],
           'statequant': lambda v: v['statequantlen'][0],
           'meanpowum': lambda v: 3 * v['ceporder'][0],
           'ivarpow': lambda v: 3 * v['ceporder'][0]}


def decompile(template, pkb):
    # newline='': the line ends of the template (LF or CRLF) are kept
    lines = open(template, encoding='utf-8', errors='replace', newline='').read().split('\n')
    out = []
    pos = 0
    vals = {}

    def take(count, size):
        nonlocal pos
        v = [int.from_bytes(pkb[pos + i * size:pos + (i + 1) * size], 'little')
             for i in range(count)]
        pos += count * size
        return v

    skipping = False
    pair = None                     # template lines of an n_comps/phase pair
    for idx, line in enumerate(lines):
        code = line.split('!', 1)[0].strip()
        if skipping and re_values.match(code):
            continue                # values of the template: replaced
        skipping = False
        m = re_spec.match(line)
        if not m or not code:
            if pair is None:
                out.append(line)
            continue
        key, count, typ = m.group(2), int(m.group(4)), m.group(6)
        if key == 'n_comps':
            if pair is None:
                # the pairs of the phase pdf: generated from the data
                nxt = next(lines[k] for k in range(idx + 1, len(lines))
                           if re_spec.match(lines[k]) and 'phase' in lines[k])
                pair = (m, re_spec.match(nxt))
                pm, qm = pair
                peol = '\r' if pm.group(0).endswith('\r') else ''
                qeol = '\r' if qm.group(0).endswith('\r') else ''
                for _ in range(vals['numvectors'][0]):
                    n, = take(1, 1)
                    out.append(pm.group(1) + 'n_comps' + pm.group(3) + '1' + pm.group(5) +
                               pm.group(6) + pm.group(7))
                    out.append(str(n) + peol)
                    out.append(qm.group(1) + 'phase' + qm.group(3) + str(n) + qm.group(5) +
                               qm.group(6) + qm.group(7))
                    out.extend(str(x) + qeol for x in take(n, 1))
            skipping = True
            continue
        if pair is not None:
            skipping = True         # the rest of the template pairs
            continue
        size = TYPES[typ]
        if key in DEPENDS:
            count = DEPENDS[key](vals)
        elif key == 'index':
            count = vals['numvectors'][0]
        elif key == 'content':
            count = (len(pkb) - pos) // size
        vals[key] = take(count, size)
        eol = '\r' if line.endswith('\r') else ''
        out.append(m.group(1) + key + m.group(3) + str(count) + m.group(5) + typ + m.group(7))
        out.extend(str(v) + eol for v in vals[key])
        skipping = True
    if pos != len(pkb):
        raise ValueError('%d bytes of the pkb not covered by the template' % (len(pkb) - pos))
    return '\n'.join(out), vals


def main():
    text, vals = decompile(sys.argv[1], open(sys.argv[2], 'rb').read())
    open(sys.argv[3], 'w', encoding='utf-8', newline='').write(text)


if __name__ == '__main__':
    main()
