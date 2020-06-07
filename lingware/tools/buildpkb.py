#!/usr/bin/env python3
#############################################################################
# python script buildpkb.py --- builds textana and siggen lingware pkb files
#                               from utf text files
#
# Based on buildpkb.sh from SVOX
#############################################################################

import argparse
import subprocess
import sys

# init
args = argparse.Namespace()

parser = argparse.ArgumentParser(add_help = False)
parser.add_argument('language', type = str,
                    help = 'language, e.g. en')
parser.add_argument('countryid', type = str,
                    help = 'country id, e.g. GB')
parser.add_argument('voice', type = str,
                    help = 'voice, e.g. kh0')

parser.parse_args(namespace = args)

if not args.language:
    print('*** error: language is required')
    exit(1)

if not args.countryid:
    print('*** error: countryid is rquired')
    exit(1)

if not args.voice:
    print('*** error: voice is required')
    exit(1)

#tools
TOOLS_DIR = '.'

#textana sources
TA_SRC_DIR = '../textana'

#siggen sources
SG_SRC_DIR = '../siggen'

#resulting pkb
DEST_PKB_DIR = '../pkb'

#temporary files
TMP_DIR = '.'

#### check if language supported
validcountries = {'en': ['GB', 'US'],
                  'fr': ['FR'],
                  'es': ['ES'],
                  'it': ['IT'],
                  'de': ['DE'],
                  }

validlangs = {'en-GB': {'wpho_range': ['1'], 'spho_range': ['1', '2', '3', '4'], 'voice': {'kh0': ['5']} },
              'en-US': {'wpho_range': ['1', '2'], 'spho_range': ['1', '2'], 'voice': {'lh0': ['2', '3', '4', '5']} },
              'fr-FR': {'wpho_range': ['1'], 'spho_range': ['1', '2', '3', '4', '5', '6', '7', '8'], 'voice': {'nk0': ['9']} },
              'es-ES': {'wpho_range': ['1'], 'spho_range': ['1', '2', '3', '4'], 'voice': {'zl0': ['5']} },
              'it-IT': {'wpho_range': ['1'], 'spho_range': ['1'], 'voice': {'cm0': ['2']} },
              'de-DE': {'wpho_range': ['1', '2'], 'spho_range': ['1'], 'voice': {'gl0': ['2']} },
              }

# check if language supported
if args.language in validcountries:
    if args.countryid in validcountries.get(args.language):
        pass
    else:
        print('invalid country for language ' + args.language)
        exit(1)
else:
    print('invalid language: ' + args.language)
    exit(1)

LANG = args.language + '-' + args.countryid
VOICE = args.voice

###########################################
##
## SET LANGUAGE-DEPENDENT PARAMS
##
###########################################

if LANG in validlangs:
    WPHO_RANGE = validlangs.get(LANG).get('wpho_range')
    SPHO_RANGE = validlangs.get(LANG).get('spho_range')
    if VOICE in validlangs.get(LANG).get('voice'):
        SPHO_VOICE_RANGE = validlangs.get(LANG).get('voice').get(VOICE)
    else:
        print('Error <voice> is incorrect')
        exit(1)

TA_SRC_DIR_LANG = TA_SRC_DIR + '/' + LANG + '/'
SG_SRC_DIR_LANG = SG_SRC_DIR + '/' + LANG + '/'

DEST_PKB_DIR_LANG = DEST_PKB_DIR + '/' + LANG + '/'

## language-independent values
LFZ_RANGE = ['1', '2', '3', '4', '5']
MGC_RANGE = ['1', '2', '3', '4', '5']

###########################################
##
## DEFINE FILE NAMES
##
###########################################

#####  TABLES / LEXICON ###################

GRAPHS_FN = LANG + '_graphs.utf'
PHONES_FN = LANG + '_phones.utf'
POS_FN = LANG + '_pos.utf'

LEXPOS_FN = LANG + '_lexpos.utf'

GRAPHS_PKB_FN = LANG + '_ktab_graphs.pkb'
PHONES_PKB_FN = LANG + '_ktab_phones.pkb'
POS_PKB_FN = LANG + '_ktab_pos.pkb'

LEXPOS_PKB_FN = LANG + '_klex.pkb'

DBG_PKB_FN = LANG + '_kdbg.pkb'

#####  AUTOMATA  ########################

# phonetic input alphabet parser
PARSE_XSAMPA = 'parse-xsampa'

PARSE_XSAMPA_SYM_FN = PARSE_XSAMPA + '_symtab.utf'
PARSE_XSAMPA_AUT_FN = PARSE_XSAMPA + '_aut.utf'

PARSE_XSAMPA_AUT_PKB_FN = 'kfst_' + PARSE_XSAMPA + '.pkb'

# phonetic input alphabet to internal phonemes mapper
MAP_XSAMPA = 'map-xsampa'

MAP_XSAMPA_SYM_FN = LANG + '_' + MAP_XSAMPA + '_symtab.utf'
MAP_XSAMPA_AUT_FN = LANG + '_' + MAP_XSAMPA + '_aut.utf'

MAP_XSAMPA_AUT_PKB_FN = LANG + '_kfst_' + MAP_XSAMPA + '.pkb'

AUT_WORD_FN = {}
AUT_PKB_WORD_FN = {}
for i in WPHO_RANGE:
    AUT_WORD_FN[i] = LANG + '_aut_wpho' + i + '.utf'
    AUT_PKB_WORD_FN[i] = LANG + '_kfst_wpho' + i + '.pkb'

AUT_SENT_FN = {}
AUT_PKB_SENT_FN = {}
for i in SPHO_RANGE:
    AUT_SENT_FN[i] = LANG + '_aut_spho' + i + '.utf'
    AUT_PKB_SENT_FN[i] = LANG + '_kfst_spho' + i + '.pkb'

# voice dependent FSTs
for i in SPHO_VOICE_RANGE:
    AUT_SENT_FN[i] = LANG + '_' + VOICE + '_aut_spho' + i + '.utf'
    AUT_PKB_SENT_FN[i] = LANG + '_' + VOICE + '_kfst_spho' + i + '.pkb'

PHONES_SYM_FN = LANG + '_phones_symtab.utf'

#####  PREPROC  ###########################

TPP_NET_FN = LANG + '_tpp_net.utf'
TPP_NET_PKB_FN = LANG + '_kpr.pkb'

#####  DECISION TREES  ####################

#textana DT
DT_POSP_FN = LANG + '_kdt_posp.utf'
DT_POSD_FN = LANG + '_kdt_posd.utf'
DT_G2P_FN = LANG + '_kdt_g2p.utf'
DT_PHR_FN = LANG + '_kdt_phr.utf'
DT_ACC_FN = LANG + '_kdt_acc.utf'

#textana configuration ini files
CFG_POSP_FN = LANG + '_kdt_posp.dtfmt'
CFG_POSD_FN = LANG + '_kdt_posd.dtfmt'
CFG_G2P_FN = LANG + '_kdt_g2p.dtfmt'
CFG_PHR_FN = LANG + '_kdt_phr.dtfmt'
CFG_ACC_FN = LANG + '_kdt_acc.dtfmt'

DT_PKB_POSP_FN = LANG + '_kdt_posp.pkb'
DT_PKB_POSD_FN = LANG + '_kdt_posd.pkb'
DT_PKB_G2P_FN = LANG + '_kdt_g2p.pkb'
DT_PKB_PHR_FN = LANG + '_kdt_phr.pkb'
DT_PKB_ACC_FN = LANG + '_kdt_acc.pkb'

#siggen DT
DT_DUR_FN = LANG + '_' + VOICE + '_kdt_dur.utf'
DT_PKB_DUR_FN = LANG + '_' + VOICE + '_kdt_dur.pkb'

DT_LFZ_FN = {}
DT_PKB_LFZ_FN = {}
for i in LFZ_RANGE:
    DT_LFZ_FN[i] = LANG + '_' + VOICE + '_kdt_lfz' + i + '.utf'
    DT_PKB_LFZ_FN[i] = LANG + '_' + VOICE + '_kdt_lfz' + i + '.pkb'

DT_MGC_FN = {}
DT_PKB_MGC_FN = {}
for i in MGC_RANGE:
    DT_MGC_FN[i] = LANG + '_' + VOICE + '_kdt_mgc' + i + '.utf'
    DT_PKB_MGC_FN[i] = LANG + '_' + VOICE + '_kdt_mgc' + i + '.pkb'

#siggen configuration ini file
CFG_SG_FN = 'kdt_pam.dtfmt'

#####  PDFS  ##############################

PDF_DUR_FN = LANG + '_' + VOICE + '_kpdf_dur.utf'
PDF_LFZ_FN = LANG + '_' + VOICE + '_kpdf_lfz.utf'
PDF_MGC_FN = LANG + '_' + VOICE + '_kpdf_mgc.utf'
PDF_PHS_FN = LANG + '_' + VOICE + '_kpdf_phs.utf'

PDF_PKB_DUR_FN = LANG + '_' + VOICE + '_kpdf_dur.pkb'
PDF_PKB_LFZ_FN = LANG + '_' + VOICE + '_kpdf_lfz.pkb'
PDF_PKB_MGC_FN = LANG + '_' + VOICE + '_kpdf_mgc.pkb'
PDF_PKB_PHS_FN = LANG + '_' + VOICE + '_kpdf_phs.pkb'

###########################################
##
## DEFINE FULL FILE PATHS
##
###########################################

#####  TABLES / LEXICA   ##################

SRC_GRAPHS = TA_SRC_DIR_LANG + '/' + GRAPHS_FN
DEST_PKB_GRAPHS = DEST_PKB_DIR_LANG + '/' + GRAPHS_PKB_FN

SRC_PHONES = TA_SRC_DIR_LANG + '/' + PHONES_FN
DEST_PKB_PHONES = DEST_PKB_DIR_LANG + '/' + PHONES_PKB_FN

SRC_POS = TA_SRC_DIR_LANG + '/' + POS_FN
DEST_PKB_POS = DEST_PKB_DIR_LANG + '/' + POS_PKB_FN

SRC_LEX = TA_SRC_DIR_LANG + '/' + LEXPOS_FN
DEST_PKB_LEX = DEST_PKB_DIR_LANG + '/' + LEXPOS_PKB_FN

DEST_PKB_DBG = DEST_PKB_DIR_LANG + '/' + DBG_PKB_FN

#####  AUTOMATA  ########################

SRC_PARSE_XSAMPA_AUT = TA_SRC_DIR + '/' + PARSE_XSAMPA_AUT_FN
SRC_PARSE_XSAMPA_SYM = TA_SRC_DIR + '/' + PARSE_XSAMPA_SYM_FN

DEST_PARSE_XSAMPA_AUT_PKB = DEST_PKB_DIR + '/' + PARSE_XSAMPA_AUT_PKB_FN

SRC_MAP_XSAMPA_AUT = TA_SRC_DIR_LANG + '/' + MAP_XSAMPA_AUT_FN
SRC_MAP_XSAMPA_SYM = TA_SRC_DIR_LANG + '/' + MAP_XSAMPA_SYM_FN

DEST_MAP_XSAMPA_AUT_PKB = DEST_PKB_DIR_LANG + '/' + MAP_XSAMPA_AUT_PKB_FN

SRC_AUT_WORD = {}
DEST_AUT_PKB_WORD = {}
for i in WPHO_RANGE:
    SRC_AUT_WORD[i] = TA_SRC_DIR_LANG + '/' +AUT_WORD_FN[i]
    DEST_AUT_PKB_WORD[i] = DEST_PKB_DIR_LANG + '/' + AUT_PKB_WORD_FN[i]

SRC_AUT_SENT = {}
DEST_AUT_PKB_SENT = {}
for i in SPHO_RANGE:
    SRC_AUT_SENT[i] = TA_SRC_DIR_LANG + '/' + AUT_SENT_FN[i]
    DEST_AUT_PKB_SENT[i] = DEST_PKB_DIR_LANG + '/' + AUT_PKB_SENT_FN[i]

#voice dependent FSTs
for i in SPHO_VOICE_RANGE:
    SRC_AUT_SENT[i] = TA_SRC_DIR_LANG + '/' + AUT_SENT_FN[i]
    DEST_AUT_PKB_SENT[i] = DEST_PKB_DIR_LANG + '/' + AUT_PKB_SENT_FN[i]

TMP_PHONES_SYM = TMP_DIR + '/' + PHONES_SYM_FN

#####  PREPROC  ###########################

SRC_TPP_NET = TA_SRC_DIR_LANG + '/' + TPP_NET_FN
DEST_TPP_NET_PKB = DEST_PKB_DIR_LANG + '/' + TPP_NET_PKB_FN

#####  DECISION TREES  ####################

#textana DT
SRC_DT_POSP = TA_SRC_DIR_LANG + '/' + DT_POSP_FN
SRC_DT_POSD = TA_SRC_DIR_LANG + '/' + DT_POSD_FN
SRC_DT_G2P = TA_SRC_DIR_LANG + '/' + DT_G2P_FN
SRC_DT_PHR = TA_SRC_DIR_LANG + '/' + DT_PHR_FN
SRC_DT_ACC = TA_SRC_DIR_LANG + '/' + DT_ACC_FN

#textana configuration ini files
CFG_DT_POSP = TA_SRC_DIR_LANG + '/' + CFG_POSP_FN
CFG_DT_POSD = TA_SRC_DIR_LANG + '/' + CFG_POSD_FN
CFG_DT_G2P = TA_SRC_DIR_LANG + '/' + CFG_G2P_FN
CFG_DT_PHR = TA_SRC_DIR_LANG + '/' + CFG_PHR_FN
CFG_DT_ACC = TA_SRC_DIR_LANG + '/' + CFG_ACC_FN

#siggen
SRC_DT_DUR = SG_SRC_DIR_LANG + '/' + DT_DUR_FN

SRC_DT_LFZ = {}
for i in LFZ_RANGE:
    SRC_DT_LFZ[i] = SG_SRC_DIR_LANG + '/' + DT_LFZ_FN[i]

SRC_DT_MGC = {}
for i in MGC_RANGE:
    SRC_DT_MGC[i] = SG_SRC_DIR_LANG + '/' + DT_MGC_FN[i]

#siggen configuration ini file
CFG_DT_SG = SG_SRC_DIR + '/' + CFG_SG_FN

#textana
DEST_DT_PKB_POSP = DEST_PKB_DIR_LANG + '/' + DT_PKB_POSP_FN
DEST_DT_PKB_POSD = DEST_PKB_DIR_LANG + '/' + DT_PKB_POSD_FN
DEST_DT_PKB_G2P = DEST_PKB_DIR_LANG + '/' + DT_PKB_G2P_FN
DEST_DT_PKB_PHR = DEST_PKB_DIR_LANG + '/' + DT_PKB_PHR_FN
DEST_DT_PKB_ACC = DEST_PKB_DIR_LANG + '/' + DT_PKB_ACC_FN


#siggen
DEST_DT_PKB_DUR = DEST_PKB_DIR_LANG + '/' + DT_PKB_DUR_FN
    
DEST_DT_PKB_LFZ = {}
for i in LFZ_RANGE:
    DEST_DT_PKB_LFZ[i] = DEST_PKB_DIR_LANG + '/' + DT_PKB_LFZ_FN[i]

DEST_DT_PKB_MGC = {}
for i in MGC_RANGE:
    DEST_DT_PKB_MGC[i] = DEST_PKB_DIR_LANG + '/' + DT_PKB_MGC_FN[i]

#####  PDFS  ##############################

SRC_PDF_DUR = SG_SRC_DIR_LANG + '/' + PDF_DUR_FN
SRC_PDF_LFZ = SG_SRC_DIR_LANG + '/' + PDF_LFZ_FN
SRC_PDF_MGC = SG_SRC_DIR_LANG + '/' + PDF_MGC_FN
SRC_PDF_PHS = SG_SRC_DIR_LANG + '/' + PDF_PHS_FN

DEST_PDF_PKB_DUR = DEST_PKB_DIR_LANG + '/' + PDF_PKB_DUR_FN
DEST_PDF_PKB_LFZ = DEST_PKB_DIR_LANG + '/' + PDF_PKB_LFZ_FN
DEST_PDF_PKB_MGC = DEST_PKB_DIR_LANG + '/' + PDF_PKB_MGC_FN
DEST_PDF_PKB_PHS = DEST_PKB_DIR_LANG + '/' + PDF_PKB_PHS_FN

###########################################
##
## Compilation into pkb
##
###########################################

SYMSHIFT = TOOLS_DIR + '/symshift.pl'
GRAPHS_TO_PKB = TOOLS_DIR + '/picoloadgraphs.py'
PHONES_TO_PKB = TOOLS_DIR + '/picoloadphones.py'
DBG_TO_PKB = TOOLS_DIR + '/picoloaddbg.py'
POS_TO_PKB = TOOLS_DIR + '/picoloadpos.py'
LEX_TO_PKB = TOOLS_DIR + '/picoloadlex.exe'
AUT_TO_PKB = TOOLS_DIR + '/picoloadfst.exe'
TPP_TO_PKB = TOOLS_DIR + '/picoloadpreproc.exe'
DT_TO_PKB = TOOLS_DIR + '/dt2pkb.exe'
PDF_TO_PKB = TOOLS_DIR + '/pdf2pkb.exe'

##### build intermediate files ############################

print(SYMSHIFT + ' -phones ' + SRC_PHONES + ' -POS ' + SRC_POS + ' > ' + TMP_PHONES_SYM, flush=True)
subprocess.run(['perl', SYMSHIFT, '-phones', SRC_PHONES, '-POS', SRC_POS, '>', TMP_PHONES_SYM], shell=True)

#####  TABLES  ############################

print(GRAPHS_TO_PKB + ' ' + SRC_GRAPHS + ' ' + DEST_PKB_GRAPHS, flush=True)
subprocess.run([sys.executable, GRAPHS_TO_PKB, SRC_GRAPHS, DEST_PKB_GRAPHS])

print(PHONES_TO_PKB + ' ' + SRC_PHONES + ' ' + DEST_PKB_PHONES, flush=True)
subprocess.run([sys.executable, PHONES_TO_PKB, SRC_PHONES, DEST_PKB_PHONES])

print(POS_TO_PKB + ' ' + SRC_POS + ' ' + DEST_PKB_POS, flush=True)
subprocess.run([sys.executable, POS_TO_PKB, SRC_POS, DEST_PKB_POS])

print(DBG_TO_PKB + ' ' + SRC_PHONES + ' ' + DEST_PKB_DBG, flush=True)
subprocess.run([sys.executable, DBG_TO_PKB, SRC_PHONES, DEST_PKB_DBG])

#####  LEXICON ############################

print(LEX_TO_PKB + ' ' + SRC_PHONES + ' ' + SRC_POS + ' ' + SRC_LEX + ' ' + DEST_PKB_LEX, flush=True)
subprocess.run([LEX_TO_PKB, SRC_PHONES, SRC_POS, SRC_LEX, DEST_PKB_LEX])

#####  AUTOMATA  ########################

print(AUT_TO_PKB + ' ' + SRC_PARSE_XSAMPA_AUT  + ' ' +  SRC_PARSE_XSAMPA_SYM  + ' ' + DEST_PARSE_XSAMPA_AUT_PKB, flush=True)
subprocess.run([AUT_TO_PKB, SRC_PARSE_XSAMPA_AUT, SRC_PARSE_XSAMPA_SYM, DEST_PARSE_XSAMPA_AUT_PKB])

print(AUT_TO_PKB  + ' ' + SRC_MAP_XSAMPA_AUT + ' ' + SRC_MAP_XSAMPA_SYM + ' ' + DEST_MAP_XSAMPA_AUT_PKB, flush=True)
subprocess.run([AUT_TO_PKB, SRC_MAP_XSAMPA_AUT, SRC_MAP_XSAMPA_SYM, DEST_MAP_XSAMPA_AUT_PKB])

for i in WPHO_RANGE:
    print(AUT_TO_PKB + ' ' + SRC_AUT_WORD[i] + ' ' + TMP_PHONES_SYM + ' ' + DEST_AUT_PKB_WORD[i], flush=True)
    subprocess.run([AUT_TO_PKB, SRC_AUT_WORD[i], TMP_PHONES_SYM, DEST_AUT_PKB_WORD[i]])

for i in SPHO_RANGE:
    print(AUT_TO_PKB + ' ' + SRC_AUT_SENT[i] + ' ' + TMP_PHONES_SYM + ' ' + DEST_AUT_PKB_SENT[i], flush=True)
    subprocess.run([AUT_TO_PKB, SRC_AUT_SENT[i], TMP_PHONES_SYM, DEST_AUT_PKB_SENT[i]])

# voice dependent FSTs
for i in SPHO_VOICE_RANGE:
    print(AUT_TO_PKB + ' ' + SRC_AUT_SENT[i] + ' ' + TMP_PHONES_SYM + ' ' + DEST_AUT_PKB_SENT[i], flush=True)
    subprocess.run([AUT_TO_PKB, SRC_AUT_SENT[i], TMP_PHONES_SYM, DEST_AUT_PKB_SENT[i]])

#####  PREPROC  ###########################

print(TPP_TO_PKB + ' ' + SRC_GRAPHS + ' ' + SRC_TPP_NET + ' ' + DEST_TPP_NET_PKB, flush=True)
subprocess.run([TPP_TO_PKB, SRC_GRAPHS, SRC_TPP_NET, DEST_TPP_NET_PKB])

#####  DECISION TREES  ####################

#textana
#config file is added as the argument of the dt2pkb tool
print(DT_TO_PKB + ' ' + CFG_DT_POSP + ' ' + SRC_DT_POSP + ' ' + DEST_DT_PKB_POSP, flush=True)
subprocess.run([DT_TO_PKB,  CFG_DT_POSP, SRC_DT_POSP, DEST_DT_PKB_POSP])

print(DT_TO_PKB + ' ' + CFG_DT_POSD + ' ' + SRC_DT_POSD + ' ' + DEST_DT_PKB_POSD, flush=True)
subprocess.run([DT_TO_PKB, CFG_DT_POSD, SRC_DT_POSD, DEST_DT_PKB_POSD])

print(DT_TO_PKB + ' ' + CFG_DT_G2P + ' ' + SRC_DT_G2P + ' ' + DEST_DT_PKB_G2P, flush=True)
subprocess.run([DT_TO_PKB, CFG_DT_G2P, SRC_DT_G2P, DEST_DT_PKB_G2P])

print(DT_TO_PKB + ' ' + CFG_DT_PHR + ' ' + SRC_DT_PHR + ' ' + DEST_DT_PKB_PHR, flush=True)
subprocess.run([DT_TO_PKB, CFG_DT_PHR, SRC_DT_PHR, DEST_DT_PKB_PHR])

print(DT_TO_PKB + ' ' + CFG_DT_ACC + ' ' + SRC_DT_ACC + ' ' + DEST_DT_PKB_ACC, flush=True)
subprocess.run([DT_TO_PKB, CFG_DT_ACC, SRC_DT_ACC, DEST_DT_PKB_ACC])

#siggen
print(DT_TO_PKB + ' ' + CFG_DT_SG + ' ' + SRC_DT_DUR + ' ' + DEST_DT_PKB_DUR, flush=True)
subprocess.run([DT_TO_PKB, CFG_DT_SG, SRC_DT_DUR, DEST_DT_PKB_DUR])
    
for i in LFZ_RANGE:
    print(DT_TO_PKB + ' ' + CFG_DT_SG + ' ' + SRC_DT_LFZ[i] + ' ' + DEST_DT_PKB_LFZ[i], flush=True)
    subprocess.run([DT_TO_PKB, CFG_DT_SG, SRC_DT_LFZ[i], DEST_DT_PKB_LFZ[i]])
    
for i in MGC_RANGE:
    print(DT_TO_PKB + ' ' + CFG_DT_SG + ' ' + SRC_DT_MGC[i] + ' ' + DEST_DT_PKB_MGC[i], flush=True)
    subprocess.run([DT_TO_PKB, CFG_DT_SG, SRC_DT_MGC[i], DEST_DT_PKB_MGC[i]])

#####  PDFS  ##############################

print(PDF_TO_PKB + ' ' + SRC_PDF_DUR + ' ' + DEST_PDF_PKB_DUR, flush=True)
subprocess.run([PDF_TO_PKB, SRC_PDF_DUR, DEST_PDF_PKB_DUR])

print(PDF_TO_PKB + ' ' + SRC_PDF_LFZ + ' ' + DEST_PDF_PKB_LFZ, flush=True)
subprocess.run([PDF_TO_PKB, SRC_PDF_LFZ, DEST_PDF_PKB_LFZ])

print(PDF_TO_PKB + ' ' + SRC_PDF_MGC + ' ' + DEST_PDF_PKB_MGC, flush=True)
subprocess.run([PDF_TO_PKB, SRC_PDF_MGC, DEST_PDF_PKB_MGC])

print(PDF_TO_PKB + ' ' + SRC_PDF_PHS + ' ' + DEST_PDF_PKB_PHS, flush=True)
subprocess.run([PDF_TO_PKB, SRC_PDF_PHS, DEST_PDF_PKB_PHS])
