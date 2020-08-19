#!/usr/bin/env python3
#############################################################################
# python script buildbin.py --- builds textana and siggen lingware resources
#                               from pkb files
#
# Based on buildbin.sh from SVOX
#############################################################################

import argparse
import subprocess

# init
args = argparse.Namespace()

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('langcountryid', type=str,
                    help='language country id, e.g. en-GB')
parser.add_argument('speakerid', type=str,
                    help='speaker id, e.g. kh0')

parser.parse_args(namespace=args)

if not args.langcountryid:
    print('*** error: langcountryid is required', flush=True)
    exit(1)

if not args.speakerid:
    print('*** error: speakerid is rquired', flush=True)
    exit(1)

## version suffixes 
VERSION_SUFFIXES = {'cm0': '1.0.0.3-0-0',
                    'zl0': '1.0.0.3-0-0',
                    'gl0': '1.0.0.3-0-1',
                    'kh0': '1.0.0.3-0-0',
                    'lh0': '1.0.0.3-0-1',
                    'nk0': '1.0.0.3-0-2',
                    }

TOOLSDIR='./'
CONFIGSDIR='../configs/'
GLW = 'genlingware.pl'
LANGDIR = '../../lang/'

validlangs = {'en-GB': ['kh0'],
              'en-US': ['lh0'],
              'fr-FR': ['nk0'],
              'es-ES': ['zl0'],
              'it-IT': ['cm0'],
              'de-DE': ['gl0'],
              }

# check if language supported
if args.langcountryid in validlangs:
    if args.speakerid in validlangs.get(args.langcountryid):
        VERSION_SUFFIX = VERSION_SUFFIXES[args.speakerid]
    else:
        print('invalid speaker id', flush=True)
        exit(1)

LANG = args.langcountryid
SID = args.speakerid

subprocess.run(['perl', TOOLSDIR + '/' + GLW, CONFIGSDIR + '/' + LANG + '/' + LANG + '_ta.txt', LANGDIR + '/' + LANG + '_ta_' + VERSION_SUFFIX + '.bin'])
subprocess.run(['perl', TOOLSDIR + '/' + GLW, CONFIGSDIR + '/' + LANG + '/' + LANG + '_' + SID + '_sg.txt', LANGDIR + '/' + LANG + '_' + SID + '_sg_' + VERSION_SUFFIX + '.bin'])
subprocess.run(['perl', TOOLSDIR + '/' + GLW, CONFIGSDIR + '/' + LANG + '/' + LANG + '_dbg.txt', LANGDIR + '/' + LANG + '_dbg.bin'])
