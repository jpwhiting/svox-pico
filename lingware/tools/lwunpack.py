#!/usr/bin/env python3
"""Unpack a Pico lingware .bin (genlingware.pl container) into its knowledge
bases. usage: lwunpack.py FILE.bin [OUTDIR]  (lists them without OUTDIR)

Layout (genlingware.pl): SVOX header " (C) SVOX AG " with each character
shifted down by ' ', uint16 header length, header (number of fields, fields,
fill), uint32 content size, then the content: uint8 number of kbs, the kb
names each closed by a space, a directory of (uint8 id, uint32 offset,
uint32 size) relative to the content start, a fill, and the kbs.

Licensed under the Apache License, Version 2.0
"""
import os
import struct
import sys

SVOX = bytes(ord(c) - ord(' ') for c in " (C) SVOX AG ")


def unpack(data):
    assert data.startswith(SVOX), 'not a Pico lingware file'
    p = len(SVOX)
    hlen, = struct.unpack_from('<H', data, p)
    p += 2
    header = data[p:p + hlen]
    nfields = header[0]
    fields = header[1:].split(b'\0')[0].decode('latin-1').split(' ')
    fields = dict(zip(fields[0::2], fields[1::2]))
    p += hlen
    total, = struct.unpack_from('<I', data, p)
    p += 4
    base = p
    nkb = data[p]
    p += 1
    names = []
    for _ in range(nkb):
        e = data.index(b' ', p)
        names.append(data[p:e].decode('latin-1'))
        p = e + 1
    kbs = []
    for name in names:
        kid, off, size = struct.unpack_from('<BII', data, p)
        p += 9
        kbs.append((name, kid, data[base + off:base + off + size]))
    return fields, kbs, nfields, total


def main():
    data = open(sys.argv[1], 'rb').read()
    fields, kbs, nfields, total = unpack(data)
    print(' '.join('%s=%s' % kv for kv in fields.items()))
    for name, kid, kb in kbs:
        print('  %-16s id %3d  %7d bytes' % (name, kid, len(kb)))
        if len(sys.argv) > 2:
            os.makedirs(sys.argv[2], exist_ok=True)
            open(os.path.join(sys.argv[2], name + '.pkb'), 'wb').write(kb)


if __name__ == '__main__':
    main()
