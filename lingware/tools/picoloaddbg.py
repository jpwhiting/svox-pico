#!/usr/bin/env python3
# python script picoloaddbg.py --- creates pkb containing dbg table.
#
# Based on picoloaddbg.lua script by SVOX
#
# Copyright 2020 Jeremy Whiting <jpwhiting@kde.org>
#
# load pico phones src file and create dbg pkb file
#
# accepted syntax:
# - parses line of the following format:
#   :SYM "<sym>" :PROP mapval = <uint8> { , <propname> = <int> }
# - initial '!' and trailing '!.*' are treated as comments, no '[]'

import argparse
import os

import symboltable

# valid property names
propertyNames = {
    'mapval': 0,
    'vowel': 0,
    'diphth': 0,
    'glott': 0,
    'nonsyllvowel': 0,
    'syllcons': 0
}

# valid unique property names (may occur once only)
uniquePropertyNames = {
    'primstress': 0,
    'secstress': 0,
    'syllbound': 0,
    'wordbound': 0,
    'pause': 0
}


# init
args = argparse.Namespace()

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('infile', type=argparse.FileType('r'),
                    help='source file name of dbg text data')
parser.add_argument('outfile', type=argparse.FileType('wb'),
                    help='destination file name of dbg binary data')

parser.parse_args(namespace=args)

if not args.infile:
    print("*** error: could not open input file: " + args.infile)
    exit(1)

if not args.outfile:
    print("*** error: could not open output file: " + args.outfile)
    exit(1)

# tables
# table with symbol name keys (not really used currently)
symbols = {}

# table with symbol name number keys (specified with property mapval)
symbolNumbers = {}

# array of symbol name numer keys used (to check for unique mapvals)
symbolUsed = {}

table = symboltable.SymbolTable()
symbols = table.parseFile(args.infile)
args.infile.close()

for symbol in symbols:
    properties = symbols[symbol]
    mappedValue = properties.get('mapval')

    # Parse otherProperties setting flags as appropriate
    for property in properties.keys():
        value = properties[property]
        if not property == 'mapval' and not value == 1:
            print("*** error in property list, optional properties"
                  " only accept \"1\": " + property)
            continue

    # Make sure this value isn't used yet
    if mappedValue in symbolUsed:
        print("*** error: mapval values must be unique, " +
              str(mappedValue))
    else:
        symbolUsed[mappedValue] = True

    symbolNumbers[int(mappedValue)] = symbol

# Write each symbol with 8 bytes of padding as needed
for i in range(0, 256):
    value = '' 
    if i in symbolNumbers:
        value = symbolNumbers[i]
    args.outfile.write(value.encode('utf-8'))
    bytesleft = 8 - len(value)
    for j in range(0, bytesleft):
        args.outfile.write(b'\x00')

args.outfile.close()
