#!/usr/bin/env python3
#############################################################################
# python script buildpkb.py --- builds textana and siggen lingware pkb files
#                               from utf text files
#
# Based on buildpkb.sh from SVOX.  All compilers are python reimplementations
# of the original windows tools, no wine / .exe needed.
#
#   usage: buildpkb.py <langid> <countryid> <voice>     e.g. en GB kh0
#
# The FST sets (wpho / spho / voice dependent spho) are detected from the
# files present in textana/<lang>, so new languages need no change here.
#############################################################################

import argparse
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LINGWARE = os.path.dirname(HERE)
TA_SRC_DIR = os.path.join(LINGWARE, 'textana')
SG_SRC_DIR = os.path.join(LINGWARE, 'siggen')
DEST_PKB_DIR = os.path.join(LINGWARE, 'pkb')
TMP_DIR = HERE

LFZ_RANGE = MGC_RANGE = ['1', '2', '3', '4', '5']


def tool(name):
    return [sys.executable, os.path.join(HERE, name)]


def run(cmd, stdout=None):
    print(' '.join(os.path.relpath(c, HERE) if os.path.isabs(c) else c for c in cmd[1:]),
          flush=True)
    r = subprocess.run(cmd, stdout=stdout)
    if r.returncode != 0:
        print('*** error: command failed: %s' % ' '.join(cmd), flush=True)
        sys.exit(1)


def numbered(pattern, rx):
    res = []
    for f in glob.glob(pattern):
        m = re.search(rx, os.path.basename(f))
        if m:
            res.append((int(m.group(1)), f))
    return sorted(res)


def main():
    ap = argparse.ArgumentParser(description='build Pico lingware pkb files')
    ap.add_argument('language', help='language, e.g. en')
    ap.add_argument('countryid', help='country id, e.g. GB')
    ap.add_argument('voice', help='voice, e.g. kh0')
    a = ap.parse_args()

    LANG = a.language + '-' + a.countryid
    VOICE = a.voice
    ta = os.path.join(TA_SRC_DIR, LANG)
    sg = os.path.join(SG_SRC_DIR, LANG)
    dst = os.path.join(DEST_PKB_DIR, LANG)
    if not os.path.isdir(ta):
        print('*** error: no sources for language %s' % LANG)
        sys.exit(1)
    os.makedirs(dst, exist_ok=True)

    def T(name):
        return os.path.join(ta, LANG + '_' + name)

    def P(name):
        return os.path.join(dst, LANG + '_' + name)

    phones = T('phones.utf')
    pos = T('pos.utf')
    graphs = T('graphs.utf')
    phones_sym = os.path.join(TMP_DIR, LANG + '_phones_symtab.utf')

    ##### intermediate symbol table for the phonetic FSTs
    with open(phones_sym, 'w') as f:
        run(['perl', os.path.join(HERE, 'symshift.pl'), '-phones', phones, '-POS', pos],
            stdout=f)

    ##### tables
    run(tool('picoloadgraphs.py') + [graphs, P('ktab_graphs.pkb')])
    run(tool('picoloadphones.py') + [phones, P('ktab_phones.pkb')])
    run(tool('picoloadpos.py') + [pos, P('ktab_pos.pkb')])
    run(tool('picoloaddbg.py') + [phones, P('kdbg.pkb')])

    ##### lexicon
    run(tool('picoloadlex.py') + [phones, pos, T('lexpos.utf'), P('klex.pkb')])

    ##### automata
    run(tool('picoloadfst.py') + [os.path.join(TA_SRC_DIR, 'parse-xsampa_aut.utf'),
                                  os.path.join(TA_SRC_DIR, 'parse-xsampa_symtab.utf'),
                                  os.path.join(DEST_PKB_DIR, 'kfst_parse-xsampa.pkb')])
    if os.path.exists(T('map-xsampa_aut.utf')):
        run(tool('picoloadfst.py') + [T('map-xsampa_aut.utf'), T('map-xsampa_symtab.utf'),
                                      P('kfst_map-xsampa.pkb')])
    for i, f in numbered(os.path.join(ta, LANG + '_aut_wpho*.utf'), r'_aut_wpho(\d+)\.utf$'):
        run(tool('picoloadfst.py') + [f, phones_sym, P('kfst_wpho%d.pkb' % i)])
    for i, f in numbered(os.path.join(ta, LANG + '_aut_spho*.utf'), r'_aut_spho(\d+)\.utf$'):
        run(tool('picoloadfst.py') + [f, phones_sym, P('kfst_spho%d.pkb' % i)])
    for i, f in numbered(os.path.join(ta, LANG + '_' + VOICE + '_aut_spho*.utf'),
                         r'_aut_spho(\d+)\.utf$'):
        run(tool('picoloadfst.py') + [f, phones_sym,
                                      os.path.join(dst, '%s_%s_kfst_spho%d.pkb' % (LANG, VOICE, i))])

    ##### preprocessing
    if os.path.exists(T('tpp_net.utf')):
        run(tool('picoloadpreproc.py') + [T('tpp_net.utf'), P('kpr.pkb')])

    ##### decision trees (textana)
    for k in ('posp', 'posd', 'g2p', 'phr', 'acc'):
        run(tool('dt2pkb.py') + [T('kdt_%s.dtfmt' % k), T('kdt_%s.utf' % k), P('kdt_%s.pkb' % k)])

    if not os.path.isdir(sg):
        print('no siggen sources for %s, skipping voice' % LANG)
        return

    ##### decision trees (siggen)
    cfg = os.path.join(SG_SRC_DIR, 'kdt_pam.dtfmt')
    trees = ['dur'] + ['lfz' + i for i in LFZ_RANGE] + ['mgc' + i for i in MGC_RANGE]
    for k in trees:
        src = os.path.join(sg, '%s_%s_kdt_%s.utf' % (LANG, VOICE, k))
        run(tool('dt2pkb.py') + [cfg, src, os.path.join(dst, '%s_%s_kdt_%s.pkb' % (LANG, VOICE, k))])

    ##### pdfs
    for k in ('dur', 'lfz', 'mgc', 'phs'):
        src = os.path.join(sg, '%s_%s_kpdf_%s.utf' % (LANG, VOICE, k))
        run(tool('pdf2pkb.py') + [src, os.path.join(dst, '%s_%s_kpdf_%s.pkb' % (LANG, VOICE, k))])


if __name__ == '__main__':
    main()
