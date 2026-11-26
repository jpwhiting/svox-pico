#!/usr/bin/env python3
# pdf2pkb.py --- compiles PDF (probability density function) sources to pkb
#
# Replacement for SVOX pdf2pkb.exe
#   usage: pdf2pkb <pdf_utf_file> <output_pkb>
#
# Source format (see SVOX_Pico_Lingware.pdf, chapter 7 and file headers):
#   line_empty   : empty line
#   line_comment : '! comment'
#   line_section : '[duration]' | '[pitch]' | '[cepstral]' | '[phase]'
#   line_spec    : key = <number of values> , uint8|uint16|uint32 ;
#   line_value   : <unsigned number>
# The values of all specs are written in file order as little endian
# unsigned integers of the given size.
#
# Licensed under the Apache License, Version 2.0

import argparse
import re
import sys

TYPES = {'uint8': 1, 'uint16': 2, 'uint32': 4}
SECTIONS = ('duration', 'pitch', 'cepstral', 'phase')

re_section = re.compile(r'^\[\s*(\w+)\s*\]$')
re_spec = re.compile(r'^(\w+)\s*=\s*(\d+)\s*,\s*(\w+)\s*;?$')
re_values = re.compile(r'^[-+]?\d+(\s+[-+]?\d+)*$')


def compile_pdf(path):
    out = bytearray()
    section = None
    pending = []          # list of [key, remaining, size]
    with open(path, encoding='utf-8', errors='replace') as f:
        for lineno, line in enumerate(f, 1):
            line = line.split('!', 1)[0].strip()
            if not line:
                continue
            m = re_section.match(line)
            if m:
                if m.group(1) not in SECTIONS:
                    raise ValueError('%s(%d): unknown section %s' % (path, lineno, m.group(1)))
                section = m.group(1)
                continue
            m = re_spec.match(line)
            if m:
                if pending and pending[0][1] > 0:
                    raise ValueError('%s(%d): %d values missing for %s'
                                     % (path, lineno, pending[0][1], pending[0][0]))
                if section is None:
                    raise ValueError('%s(%d): spec outside of section' % (path, lineno))
                if m.group(3) not in TYPES:
                    raise ValueError('%s(%d): invalid data type %s' % (path, lineno, m.group(3)))
                pending = [[m.group(1), int(m.group(2)), TYPES[m.group(3)]]]
                continue
            if re_values.match(line):
                for tok in line.split():
                    if not pending or pending[0][1] <= 0:
                        raise ValueError('%s(%d): unexpected value' % (path, lineno))
                    v = int(tok)
                    size = pending[0][2]
                    if v < 0:
                        v += 1 << (8 * size)
                    if not 0 <= v < (1 << (8 * size)):
                        raise ValueError('%s(%d): value %s out of range' % (path, lineno, tok))
                    out += v.to_bytes(size, 'little')
                    pending[0][1] -= 1
                continue
            raise ValueError('%s(%d): syntax error: %s' % (path, lineno, line))
    if pending and pending[0][1] > 0:
        raise ValueError('%s: %d values missing for %s' % (path, pending[0][1], pending[0][0]))
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description='compile Pico pdf source to pkb')
    ap.add_argument('infile')
    ap.add_argument('outfile')
    a = ap.parse_args()
    print('*** pdf-to-pkb compiler ***')
    try:
        data = compile_pdf(a.infile)
    except ValueError as e:
        print('*** error: %s' % e, file=sys.stderr)
        sys.exit(1)
    with open(a.outfile, 'wb') as f:
        f.write(data)
    print('Program terminated successfully')


if __name__ == '__main__':
    main()
