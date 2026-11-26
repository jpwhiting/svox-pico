#!/usr/bin/env python3
# proptable.py --- parser for Pico property table source files
#
#   PropertyTableFile = { Entry } .
#   Entry = ":SYM" Symbol ":PROP" Property { "," Property } .
#   Property = Ident "=" ( INT | String ) .
#
# Licensed under the Apache License, Version 2.0

from collections import OrderedDict

import picoscanner as sc


def parse_file(path):
    """Return OrderedDict symbol -> OrderedDict(prop -> value)."""
    text = sc.read_text(path)
    p = sc.Parser(sc.tokenize(text, path), path)
    table = OrderedDict()
    while not p.at(sc.EOF):
        p.expect(sc.KW, 'SYM', 'keyword SYM')
        sym = p.expect(sc.STR, what='string').value
        p.expect(sc.KW, 'PROP', 'keyword PROP')
        props = OrderedDict()
        while True:
            name = p.expect(sc.ID, what='property identifier').value
            p.expect(sc.PUNCT, '=', "'='")
            if p.at(sc.INT) or p.at(sc.STR):
                props[name] = p.next().value
            else:
                p.error('property value expected')
            if not p.accept(sc.PUNCT, ','):
                break
        table[sym] = props
    return table


class PhoneTable:
    """Phones table: symbol <-> mapval plus longest-match transcription."""

    def __init__(self, path):
        self.table = parse_file(path)
        self.sym2id = OrderedDict()
        for s, pr in self.table.items():
            if 'mapval' not in pr:
                raise sc.ScanError('%s: no mapval for symbol %s' % (path, s))
            self.sym2id[s] = int(pr['mapval'])
        self.maxlen = max(len(s) for s in self.sym2id)

    def transcribe(self, phonstr):
        """Split phonetic string into phone ids, longest match first.

        Returns list of ids or None if not parsable."""
        res = []
        i = 0
        n = len(phonstr)
        while i < n:
            for L in range(min(self.maxlen, n - i), 0, -1):
                sid = self.sym2id.get(phonstr[i:i + L])
                if sid is not None:
                    res.append(sid)
                    i += L
                    break
            else:
                return None
        return res


class PosTable:
    """Part-of-speech table incl. combined (ambiguous) tags."""

    def __init__(self, path):
        self.table = parse_file(path)
        self.sym2id = OrderedDict()
        self.combined = {}
        for s, pr in self.table.items():
            self.sym2id[s] = int(pr['mapval'])
        for s, pr in self.table.items():
            if int(pr.get('iscombined', 0)):
                parts = frozenset(self.sym2id[x] for x in s.split('^'))
                self.combined[parts] = int(pr['mapval'])

    def lookup(self, tag):
        """mapval for (possibly combined) tag; order of parts irrelevant."""
        if tag in self.sym2id:
            return self.sym2id[tag]
        parts = tag.split('^')
        if len(parts) > 1:
            try:
                key = frozenset(self.sym2id[x] for x in parts)
            except KeyError:
                return None
            return self.combined.get(key)
        return None
