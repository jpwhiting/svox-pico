#!/usr/bin/env python3
#############################################################################
# python script buildbin.py --- builds textana and siggen lingware resources
#                               from pkb files
#
# Based on buildbin.sh from SVOX
#   usage: buildbin.py <langcountryid> <speakerid>     e.g. en-GB kh0
#############################################################################

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIGSDIR = os.path.join(HERE, '..', 'configs')
LANGDIR = os.path.join(HERE, '..', '..', 'lang')
GLW = os.path.join(HERE, 'genlingware.pl')

## version suffixes of the SVOX lingware (1.1.0.0, as in the Android tree)
VERSION_SUFFIXES = {'cm0': '1.1.0.0-0-1',
                    'zl0': '1.1.0.0-0-2',
                    'gl0': '1.1.0.0-0-2',
                    'kh0': '1.1.0.0-0-1',
                    'lh0': '1.1.0.0-0-2',
                    'nk0': '1.1.0.0-0-2',
                    }
DEFAULT_SUFFIX = '1.1.0.0-0-0'


def main():
    ap = argparse.ArgumentParser(description='build Pico lingware bin files')
    ap.add_argument('langcountryid', help='e.g. en-GB')
    ap.add_argument('speakerid', help='e.g. kh0')
    ap.add_argument('--outdir', default=LANGDIR)
    ap.add_argument('--plain', action='store_true',
                    help='file names without version suffix (as expected by pico2wave)')
    a = ap.parse_args()

    LANG, SID = a.langcountryid, a.speakerid
    suffix = VERSION_SUFFIXES.get(SID, DEFAULT_SUFFIX)
    cfg = os.path.join(CONFIGSDIR, LANG)
    if not os.path.isfile(os.path.join(cfg, '%s_%s_sg.txt' % (LANG, SID))):
        print('invalid language / speaker id: %s %s' % (LANG, SID), flush=True)
        sys.exit(1)
    os.makedirs(a.outdir, exist_ok=True)
    sfx = '' if a.plain else '_' + suffix
    jobs = [('%s_ta.txt' % LANG, '%s_ta%s.bin' % (LANG, sfx)),
            ('%s_%s_sg.txt' % (LANG, SID), '%s_%s_sg%s.bin' % (LANG, SID, sfx)),
            ('%s_dbg.txt' % LANG, '%s_dbg.bin' % LANG)]
    for c, out in jobs:
        # the configs reference the pkbs relative to the tools directory
        r = subprocess.run(['perl', GLW, os.path.join(cfg, c),
                            os.path.abspath(os.path.join(a.outdir, out))], cwd=HERE)
        if r.returncode != 0:
            sys.exit(1)


if __name__ == '__main__':
    main()
