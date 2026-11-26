#!/usr/bin/env python3
# decompile.py --- updates the lingware sources of a voice from its .bin files
#
#   usage: decompile.py <lang> <countryid> <voice> <ta.bin> <sg.bin>
#   e.g.   decompile.py fr FR nk0 fr-FR_ta.bin fr-FR_nk0_sg.bin
#
# The knowledge bases built from the current sources (buildpkb.py) are
# compared with the ones in the given .bin files; the sources of those that
# differ are replaced by decompiled ones, written in place in textana/,
# siggen/ and configs/. Their comments are lost; everything the pkb does not
# keep (names of symbols and parts of speech, automaton names, comments of
# the pdf sources, file headers) is taken from the current sources, so the
# voice to decompile must be a version of the one in the sources. This is
# repeated until nothing changes, because some sources depend on others
# (the part of speech table names the parts of speech of the lexicon and the
# trees).
#
# Afterwards buildpkb.py and buildbin.py build .bin files with the same
# knowledge bases. The decision trees of the signal generation may differ in
# the order of values in their tables (see pkb2dt.py), with the same speech.
#
# Licensed under the Apache License, Version 2.0

import argparse
import os
import re
import subprocess
import sys

import lwunpack
import pkb2dt
import pkb2fst
import pkb2lex
import pkb2pdf
import pkb2pos
import pkb2tpp

HERE = os.path.dirname(os.path.abspath(__file__))
LW = os.path.dirname(HERE)
TA = os.path.join(LW, 'textana')
SG = os.path.join(LW, 'siggen')
CF = os.path.join(LW, 'configs')


def read_config(path):
    """kb name -> pkb path of a configs/*.txt file"""
    kbs = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'(\w+)\s+"([^"]+)"', line)
        if m:
            kbs[m.group(1)] = os.path.normpath(os.path.join(HERE, m.group(2)))
    return kbs


ORIGINAL = {}       # path -> content before the first write


def write(path, text):
    if path not in ORIGINAL and os.path.exists(path):
        ORIGINAL[path] = open(path, 'rb').read()
    with open(path, 'wb') as f:
        f.write(text.encode('utf-8', 'surrogateescape'))


def restyle(path, text):
    """the decompiled text with the comment header and the line ends of the
    source it replaces, so that only what changed shows up in a diff"""
    old = open(path, 'rb').read().decode('utf-8', 'surrogateescape').split('\n')
    header = []
    for line in old:
        if line.rstrip('\r').startswith('!'):
            header.append(line)
        else:
            break
    body_old = [l for l in old[len(header):] if l]
    eol = '\r' if sum(l.endswith('\r') for l in body_old) > len(body_old) // 2 else ''
    new = text.split('\n')
    while new and new[0].rstrip('\r').startswith('!'):
        new.pop(0)
    if new and new[-1] == '':
        new.pop()
    return '\n'.join(header + [l.rstrip('\r') + eol for l in new]) + '\n'


def replace(path, text):
    write(path, restyle(path, text))


def same(name, kb, built, attrs=None):
    if kb == built:
        return True
    if name.startswith('DT_') and attrs is not None:
        # the same tree, maybe with another value order
        try:
            return tree(attrs, kb) == tree(attrs, built)
        except ValueError:
            return False
    return False


def tree(attrs, pkb):
    """the decompiled tree with the values of each subset as a set"""
    out = []
    for line in pkb2dt.decompile(attrs, pkb).split('\n')[2:]:
        out.append(re.sub(r'subset = (\S+)',
                          lambda m: 'subset = ' + ','.join(sorted(m.group(1).split(','))), line))
    return out


class Voice:
    def __init__(self, lang, country, voice):
        self.l = '%s-%s' % (lang, country)
        self.v = voice
        self.lang, self.country = lang, country
        self.d = os.path.join(TA, self.l)

    def build(self):
        r = subprocess.run([sys.executable, 'buildpkb.py', self.lang, self.country, self.v],
                           cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if r.returncode:
            raise SystemExit('*** error: buildpkb.py failed:\n' + r.stderr[-2000:])

    def dt_attrs(self, name, kind):
        k = name.lower()[3:]
        if kind == 'sg':
            return pkb2dt.dt2pkb.parse_dtfmt(os.path.join(SG, 'kdt_pam.dtfmt'))
        return pkb2dt.dt2pkb.parse_dtfmt(os.path.join(self.d, '%s_kdt_%s.dtfmt' % (self.l, k)))

    def decompile(self, name, kind, kb):
        """write the source of one knowledge base, return the files written"""
        l, v, d = self.l, self.v, self.d
        if name == 'TAB_POS':
            p = os.path.join(d, l + '_pos.utf')
            replace(p, pkb2pos.decompile(p, kb))
            return [p]
        if name == 'LEX_MAIN':
            p = os.path.join(d, l + '_lexpos.utf')
            replace(p, pkb2lex.decompile(os.path.join(d, l + '_phones.utf'),
                                         os.path.join(d, l + '_pos.utf'), kb, template=p))
            return [p]
        if name == 'TPP_MAIN':
            p = os.path.join(d, l + '_tpp_net.utf')
            replace(p, pkb2tpp.decompile(p, kb))
            return [p]
        if name.startswith('DT_'):
            k = name.lower()[3:] if kind == 'ta' else name.lower().split('_', 1)[1]
            p = (os.path.join(d, '%s_kdt_%s.utf' % (l, k)) if kind == 'ta' else
                 os.path.join(SG, l, '%s_%s_kdt_%s.utf' % (l, v, k)))
            replace(p, pkb2dt.decompile(self.dt_attrs(name, kind), kb))
            return [p]
        if name.startswith('PDF_'):
            k = name.lower().split('_', 1)[1]
            p = os.path.join(SG, l, '%s_%s_kpdf_%s.utf' % (l, v, k))
            write(p, pkb2pdf.decompile(p, kb)[0])
            return [p]
        if name.startswith('FST_'):
            if name == 'FST_XSPA_PARSE':
                p = os.path.join(TA, 'parse-xsampa_aut.utf')
                sym = os.path.join(TA, 'parse-xsampa_symtab.utf')
            elif name == 'FST_XS2SVPA':
                p = os.path.join(d, l + '_map-xsampa_aut.utf')
                sym = os.path.join(d, l + '_map-xsampa_symtab.utf')
            else:
                m = re.match(r'FST_(WPHO|SPHO)_(\d+)$', name)
                if not m:
                    raise ValueError('no source known for %s' % name)
                part = '%s_%s' % (l, v) if kind == 'sg' else l
                p = os.path.join(d, '%s_aut_%s%s.utf' % (part, m.group(1).lower(), m.group(2)))
                sym = os.path.join(HERE, l + '_phones_symtab.utf')
            aut = re.search(r':AUTOMATON\s+"([^"]*)"',
                            open(p, encoding='utf-8', errors='replace').read())
            text, added = pkb2fst.decompile(sym, kb, aut.group(1) if aut else name,
                                            os.path.join(d, l + '_phones.utf'))
            replace(p, text)
            if added:
                if sym.endswith('_phones_symtab.utf'):
                    raise ValueError('%s uses phones not in the phones table: %s' % (name, added))
                write(sym, pkb2fst.extend_symtab(sym, added))
                return [p, sym]
            return [p]
        raise ValueError('no decompiler for %s' % name)


def set_header(cfg, fields):
    """the header fields of a configs/*.txt file (its line ends are kept)"""
    t = open(cfg, encoding='utf-8', newline='').read()
    for key in ('NAME', 'VERSION', 'DATE', 'TIME'):
        if key in fields:
            t = re.sub(r'^(%s[ \t]+)[^\s]+' % key, lambda m: m.group(1) + fields[key], t, flags=re.M)
    open(cfg, 'w', encoding='utf-8', newline='').write(t)


def main():
    ap = argparse.ArgumentParser(description='update lingware sources from .bin files')
    ap.add_argument('language')
    ap.add_argument('countryid')
    ap.add_argument('voice')
    ap.add_argument('ta_bin')
    ap.add_argument('sg_bin')
    a = ap.parse_args()
    vc = Voice(a.language, a.countryid, a.voice)
    cfgs = {'ta': os.path.join(CF, vc.l, vc.l + '_ta.txt'),
            'sg': os.path.join(CF, vc.l, '%s_%s_sg.txt' % (vc.l, vc.v))}
    bins = {}
    for kind, path in (('ta', a.ta_bin), ('sg', a.sg_bin)):
        fields, kbs, _, _ = lwunpack.unpack(open(path, 'rb').read())
        bins[kind] = (fields, [(n, k) for n, i, k in kbs])
    def differing():
        """the knowledge bases built from the sources that differ"""
        vc.build()
        todo = []
        for kind in ('ta', 'sg'):
            built = read_config(cfgs[kind])
            for name, kb in bins[kind][1]:
                path = built.get(name)
                if path is None or not os.path.exists(path):
                    raise SystemExit('*** error: %s is not in %s' % (name, cfgs[kind]))
                b = open(path, 'rb').read()
                attrs = vc.dt_attrs(name, kind) if name.startswith('DT_') else None
                if not same(name, kb, b, attrs):
                    todo.append((kind, name, kb))
        return todo

    written = set()
    forced = {}         # sources decompiled only for the new part of speech table
    for rnd in range(1, 5):
        todo = differing()
        if not todo:
            break
        # the part of speech table first: the lexicon and the text analysis
        # trees name the parts of speech by it, so they follow it
        extra = []
        if any(n == 'TAB_POS' for k, n, b in todo):
            names = {n for k, n, b in todo}
            extra = [('ta', n, kb) for n, kb in bins['ta'][1]
                     if (n == 'LEX_MAIN' or n.startswith('DT_')) and n not in names]
        todo.sort(key=lambda t: t[1] != 'TAB_POS')
        print('round %d: decompiling %s' % (rnd, ', '.join(n for k, n, b in todo + extra)))
        for kind, name, kb in todo:
            written.update(vc.decompile(name, kind, kb))
        for kind, name, kb in extra:
            paths = vc.decompile(name, kind, kb)
            written.update(paths)
            for p in paths:
                forced[p] = name
    else:
        raise SystemExit('*** error: the sources do not converge')
    # keep the original of a source decompiled only for the new part of
    # speech table when it still builds the same knowledge base
    for p, name in forced.items():
        decompiled = open(p, 'rb').read()
        open(p, 'wb').write(ORIGINAL[p])
        if differing():
            open(p, 'wb').write(decompiled)
        else:
            written.discard(p)
            print('kept the original source of %s' % name)
    differing()         # leave the pkb files of the final sources
    for kind in ('ta', 'sg'):
        set_header(cfgs[kind], bins[kind][0])
    written.update(cfgs.values())
    print('sources written:')
    for p in sorted(written):
        print('  ' + os.path.relpath(p, LW))


if __name__ == '__main__':
    main()
