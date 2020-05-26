#!/usr/bin/env python3
# python script picoloadphones.py --- creates pkb containing phones table.
#
# Based on picoloadphones.lua script by SVOX
#
# Copyright 2020 Jeremy Whiting <jpwhiting@kde.org>
#
# load pico phones src file and create phones pkb file
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
                    help='source file name of phones text data')
parser.add_argument('outfile', type=argparse.FileType('wb'),
                    help='destination file name of phones binary data')

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
        if not property == 'mapval' and not value == '1':
            print("*** error in property list, optional properties"
                  " only accept \"1\": " + property)
            continue

    # Make sure this value isn't used yet
    if mappedValue in symbolUsed:
        print("*** error: mapval values must be unique, " +
              str(mappedValue))
    else:
        symbolUsed[mappedValue] = True

    symbolNumbers[int(mappedValue)] = properties

# check symbolNumbers
def checkSymbolTable(table):
    for i in propertyNames:
        propertyNames[i] = 0

    for i in uniquePropertyNames:
        uniquePropertyNames[i] = 0

    # Check each symbol, which contains a dictionary of properties
    for element in table.values():
        # Check this symbol's properties
        for key, value in element.items():
            if key not in propertyNames and key not in uniquePropertyNames:
                print("*** error: invalid property name: " + key)
                exit(1)

            if key in propertyNames:
                propertyNames[key] = propertyNames[key] + 1
            elif key in uniquePropertyNames:
                uniquePropertyNames[key] = uniquePropertyNames[key] + 1

    for key, value in uniquePropertyNames.items():
        if value > 1:
            print("*** error: property " + key + " must be unique")
            exit(1)


checkSymbolTable(symbolNumbers)

# get IDs of unique specids
specialIDs = {}
# Initialize to 0 so 0s get written to .pkb file
for i in range(1, 9):
    specialIDs[i] = 0

uniqueKeys = {'primstress': 1,
              'secstress': 2,
              'syllbound': 3,
              'pause': 4,
              'wordbound': 5
              }

# Then set each specialIDs to which mapval it is assigned to
for key, element in symbolNumbers.items():
    for test, value in uniqueKeys.items():
        if test in element:
            specialIDs[value] = int(element['mapval'])

# write out Phones pkb
propertyValues = {'vowel': 1,
                  'diphth': 2,
                  'glott': 4,
                  'nonsyllvowel': 8,
                  'syllcons': 16
                  }


def encodeProperties(dict):
    properties = 0
    for test, value in propertyValues.items():
        if test in dict:
            properties |= value
    return properties


# First write the 8 special ids
for i in range(1, 9):
    if specialIDs[i] == 0:
        args.outfile.write(b'\x00')
    else:
        args.outfile.write(bytes([specialIDs[i]]))

# Then write the flags for each symbol
for i in range(0, 256):
    value = 0
    if i in symbolNumbers:
        value = encodeProperties(symbolNumbers[i])
    args.outfile.write(bytes([value]))

args.outfile.close()
