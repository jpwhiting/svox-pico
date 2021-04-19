#!/usr/bin/env python3
# python script picoloadpreproc.py --- creates pkb containing preproc network.
#
# Written from scratch based on SVOX specs and comparing output of picoloadpreproc.exe
#
# Copyright 2021 Jeremy Whiting <jpwhiting@kde.org>
#
# load pico preproc src file and create pkb file for the knowledge base
#
# accepted syntax:
#   See chapter 5 of SVOX_Pico_Lingware.pdf

import argparse
import os
import re
import struct

strings = []
currentStringsLength = 0
lexcats = []
contexts = []
productions = []
tokens = []
outitems = []
attrvals = []

# This needs to stay in sync with pr_OutType in picopr.c
outitemvalue = {
        "STR": 0,
        "VAR": 1,
        "ITEM": 2,
        "SPELL": 3,
        "ROMAN": 4,
        "VAL": 5,
        "LEFT": 6,
        "RIGHT": 7,
        "RLZ": 8,
        "IGNORE": 9,
        "PITCH": 10,
        "SPEED": 11,
        "VOLUME": 12,
        "VOICE": 13,
        "CONTEXT": 14,
        "SVOXPA": 15,
        "SAMPA": 16,
        "PLAY": 17,
        "USESIG": 18,
        "GENFILE": 19,
        "AUDIOEDIT": 20,
        "PARA": 21,
        "SENT": 22,
        "BREAK": 23,
        "MARK": 24,
        "CONCAT": 25,
#        "OLast
}

# This needs to stay in sync with pr_TokSetEleWP in picopr.c

tokenWP = {
    "TSEOut": 1 << 0,
    "TSEMin": 1 << 1,
    "TSEMax": 1 << 2,
    "TSELen": 1 << 3,
    "TSEVal": 1 << 4,
    "TSEStr": 1 << 5,
    "TSEHead": 1 << 6,
    "TSEMid": 1 << 7,
    "TSETail": 1 << 8,
    "TSEProd": 1 << 9,
    "TSEProdExt": 1 << 10,
    "TSEVar": 1 << 11,
    "TSELex": 1 << 12,
    "TSECost": 1 << 13,
    "TSEID": 1 << 14,
    "TSEDummy1": 1 << 15,
    "TSEDummy2": 1 << 16,
    "TSEDummy3": 1 << 17,
}

tokenNP = {
        "TSEBegin": 1 << 0,
        "TSEEnd": 1 << 1,
        "TSESpace": 1 << 2,
        "TSEDigit": 1 << 3,
        "TSELetter": 1 << 4,
        "TSEChar": 1 << 5,
        "TSESeq": 1 << 6,
        "TSECmpr": 1 << 7,
        "TSENLZ": 1 << 8,
        "TSERoman": 1 << 9,
        "TSECI": 1 << 10,
        "TSECIS": 1 << 11,
        "TSEAUC": 1 << 12,
        "TSEALC": 1 << 13,
        "TSESUC": 1 << 14,
        "TSEAccept": 1 << 15,
        "TSENext": 1 << 16,
        "TSEAltL": 1 << 17,
        "TSEAltR": 1 << 18,
}

def loadStrings(infile):
    global currentStringsLength
    stringRE = re.compile('(\\d+)\\s+"(.*)"', re.UNICODE)
    line = infile.readline()
    while line != '.\n':
        m = stringRE.match(line)
        if m == None:
            print("*** error: string line didn't match syntax: {}".format(line))
            exit(1)

        # Read offset
        offset = int(m.group(1))
        if offset != currentStringsLength:
            print("*** error: strings line {} offset doesn't match current offset {}".format(line, currentStringsLength))
            exit(1)

        # read string
        string = m.group(2)
        strings.append(string)
        currentStringsLength += len(string.encode()) + 1 # +1 for terminating 0 character

        line = infile.readline()

def loadLexcats(infile):
    stringRE = re.compile('(\\d+)\\s+(\\d+)', re.UNICODE)
    line = infile.readline()
    while line != '.\n':
        m = stringRE.match(line)
        if m == None:
            print("*** error: lexcats line {} didn't match syntax, should be 2 integers".format(line))
            exit(1)

        # read lexcat
        offset = int(m.group(1))
        value = int(m.group(2))
        lexcats.append(value)

        line = infile.readline()

def loadAttrvals(infile):
    stringRE = re.compile('(\\d+)\\s+(\\d+)', re.UNICODE)
    line = infile.readline()
    while line != '.\n':
        m = stringRE.match(line)
        if m == None:
            print("*** error: attrvals line {} didn't match syntax, should be 2 integers".format(line))
            exit(1)

        # read attrvals
        offset = int(m.group(1))
        value = int(m.group(2))
        attrvals.append(value)

        line = infile.readline()


def loadOutitems(infile):
    stringRE = re.compile('(\\d+)\\s+(\\d+)\\s+(\\w+)\\s+(\\d+)')
    line = infile.readline()
    while line != '.\n':
        m = stringRE.match(line)
        if m == None:
            print("*** error: outitems line {} didn't match syntax, should be 2 integers, type then another integer".format(line))
            exit(1)

        # read outitems
        offset = int(m.group(1))
        nextitem = int(m.group(2))
        itemtype = m.group(3)
        argument = int(m.group(4))

        if not itemtype in outitemvalue:
            print("*** error: outitem has invalid type {}".format(itemtype))
            exit(1)

        outitems.append({"next": nextitem, "type": outitemvalue[itemtype], "argument": argument})

        line = infile.readline()

def loadTokens(infile):
    stringRE = re.compile('(\\d+)\\s+{(.*)}\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)')
    line = infile.readline()
    while line != '.\n':
        m = stringRE.match(line)
        if m == None:
            print("*** error: token line {} didn't match syntax, should be int, \{tokenattributes\}, then 4 integers".format(line))
            exit(1)
        
        # read tokens
        offset = int(m.group(1))
        tokensfields = m.group(2)
        nextitem = int(m.group(3))
        leftitem = int(m.group(4))
        rightitem = int(m.group(5))
        attributes = int(m.group(6))
        np = 0
        wp = 0

        # parse token fields into np and wp values
        if tokensfields != '':
            tokenattributes = tokensfields.split(',')
            for s in tokenattributes:
                if s in tokenNP:
                    np |= tokenNP[s]
                elif s in tokenWP:
                    wp |= tokenWP[s]
                else:
                    print("*** error: token attribute invalid {} in line {}".format(s, line))
                    exit(1)

        tokens.append({"wp": wp, "np": np, "next": nextitem, "left": leftitem, "right": rightitem, "attributes": attributes})

        line = infile.readline()

def loadProductions(infile):
    stringRE = re.compile('(\\d+)\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)')
    line = infile.readline()
    while line != '.\n':
        m = stringRE.match(line)
        if m == None:
            print("*** error: production line {} didn't match syntax, should be 5 integers".format(line))
            exit(1)
        
        # read tokens
        offset = int(m.group(1))
        prefcost = int(m.group(2))
        name = int(m.group(3))
        atoken = int(m.group(4))
        etoken = int(m.group(5))

        productions.append({"prefcost": prefcost, "name": name, "atoken": atoken, "etoken": etoken, })

        line = infile.readline()


def loadContexts(infile):
    stringRE = re.compile('(\\d+)\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)')
    line = infile.readline()
    while line != '.\n':
        m = stringRE.match(line)
        if m == None:
            print("*** error: context line {} didn't match syntax, should be 4 integers".format(line))
            exit(1)
        
        # read tokens
        offset = int(m.group(1))
        name = int(m.group(2))
        netname = int(m.group(3))
        prodname = int(m.group(4))

        contexts.append({"name": name, "netname": netname, "prodname": prodname})

        line = infile.readline()


def makeRE(name, loaderfunction):
    expression = re.compile('{}\\s+(\\d+)'.format(name))
    return { "name": name, "expression": expression, "length": 0, "loader": loaderfunction}

# Comment regular expression
commentLine = re.compile('^\\s*!.*$')

# Make regular expressions for each type of section
matchers = [ makeRE("NETWORK", None),
          makeRE("STRINGS", loadStrings),
          # Lexcats aren't used in pico, but need to fill it in anyway
          makeRE("LEXCATS", loadLexcats),
          makeRE("ATTRVALS", loadAttrvals),
          makeRE("OUTITEMS", loadOutitems),
          makeRE("TOKENS", loadTokens),
          makeRE("PRODUCTIONS", loadProductions),
          makeRE("CONTEXTS", loadContexts) ]

args = argparse.Namespace()

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('infile', type=argparse.FileType('r', encoding='UTF-8'),
                    help='source file name of text preprocessing network data')
parser.add_argument('outfile', type=argparse.FileType('wb'),
                    help='destination file name of pkb data')

parser.parse_args(namespace=args)

if not args.infile:
    print("*** error: could not open input file: " + args.infile)
    exit(1)

if not args.outfile:
    print("*** error: could not open output file: " + args.outfile)
    exit(1)

# Pico does some weird set msb for positive numbers for some reason...
def valBytes(value, bytes):
    return value + (1 << ((bytes * 8) - 1))

# Parse file getting each section as we come to it, including setting sizes for headers
# Also sanity check input in case it has errors, size overflows, etc.

line = args.infile.readline()
while line:
    #    -- discard comment-only lines$
    if commentLine.match(line):
        line = args.infile.readline()
        continue

    for item in matchers:
        if item["expression"].match(line):
            if item["length"] == 0:
                item["length"] = int(item["expression"].match(line).group(1))
                if item.get("loader"):
                    # Run loader for this type
                    item.get("loader")(args.infile)
            else:
                print("*** error: Can't have multiple {} lines".format(item["name"]))
                exit(1)

    line = args.infile.readline()

# Write the pkb file header of sizes first
for i in range(0, 8):
    args.outfile.write(struct.pack('<I', matchers[i]["length"]))

# Next write out the strings themselves with null terminators
for s in strings:
    args.outfile.write(s.encode())
    args.outfile.write(struct.pack('B', 0))

# Then write out lexcats
for l in lexcats:
    # Lexcats are 2 bytes long, little endian
    value = valBytes(l, 2)
    args.outfile.write(struct.pack('<H', value))

# Then attrvals
for a in attrvals:
    # attrvals are 4 bytes long, little endian
    value = valBytes(a, 4)
    args.outfile.write(struct.pack('<I', value))

# Then out items
for item in outitems:
    # out items are 7 bytes long
    # next (2), type (1), then 4 bytes of argument
    value = valBytes(item["argument"], 4)
    args.outfile.write(struct.pack('<H', item["next"]))
    args.outfile.write(struct.pack('B', item["type"]))
    if item["type"] == 1 or item["type"] == 5: # VAR and VAL are signed, so use value
        args.outfile.write(struct.pack('<I', value))
    else:
        args.outfile.write(struct.pack('<I', item["argument"]))
    

# Then tokens

for tok in tokens:
    # write out wp
    args.outfile.write(struct.pack('<I', tok["wp"]))
    # write out np
    args.outfile.write(struct.pack('<I', tok["np"]))
    # write out next
    args.outfile.write(struct.pack('<H', tok["next"]))
    # write out left
    args.outfile.write(struct.pack('<H', tok["left"]))
    # write out right
    args.outfile.write(struct.pack('<H', tok["right"]))
    # write out attributes
    args.outfile.write(struct.pack('<H', tok["attributes"]))

# Then productions
for p in productions:
    # Apparently prefcost is signed (could be negative?) so use valBytes
    args.outfile.write(struct.pack('<I', valBytes(p["prefcost"], 4)))
    args.outfile.write(struct.pack('<I', p["name"]))
    args.outfile.write(struct.pack('<H', p["atoken"]))
    args.outfile.write(struct.pack('<H', p["etoken"]))

# Finally contexts
for c in contexts:
    args.outfile.write(struct.pack('<I', c["name"]))
    args.outfile.write(struct.pack('<I', c["netname"]))
    args.outfile.write(struct.pack('<I', c["prodname"]))

args.outfile.close()
