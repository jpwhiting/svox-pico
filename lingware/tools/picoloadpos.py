#!/usr/bin/env python3
# python script picoloadpos.py --- creates pkb containing pos table.
#
# Copyright 2020 Jeremy Whiting <jpwhiting@kde.org>
#
# load pico pos utf file and create pos pkb file
#
# accepted syntax:
# - parses line of the following format:
#   :SYM "<sym>" :PROP mapval = <uint8> { , <propname> = <int> }
# - initial '!' and trailing '!.*' are treated as comments, no '[]'

import argparse
import os
import struct

# symboltable used to parse utf input files
import symboltable

# valid property names
propertyNames = {
    'mapval': 0,
    'iscombined': 0,
    'values': 0
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
# table with all symbols read from pos file
partsOfSpeech = {}

# table with symbol name keys used to do lookup of combined symbols
primaryPartsOfSpeech = {}

# table of combined symbols key is how many symbols were combined (2-8)
# single parts of speech are in partsOfSpeech, 2-8 symbol combinations are
# here
combinations = {}

# array of symbol name numer keys used (to check for unique mapvals)
symbolUsed = {}

table = symboltable.SymbolTable()
partsOfSpeech = table.parseFile(args.infile)
args.infile.close()

# parse dictionary checking for invalid values, duplicates, etc.
for symbol in partsOfSpeech.keys():
    properties = partsOfSpeech[symbol]
    mapValue = properties.get('mapval')
    if mapValue:
        for property in properties.keys():
            if property != 'mapval' and properties[property] != '1':
                # Parse otherProperties setting flags as appropriate
                print("*** error in property list, optional properties"
                      " only accept \"1\": " + property)
                continue

            else:
                pass

        # Make sure this value isn't used yet
        if mapValue in symbolUsed:
            print("*** error: mapval values must be unique, symbol: " +
                  symbol + ", value: " + str(mapValue))
        else:
            symbolUsed[mapValue] = True

        # Only add to partsOfSpeech list if it's not a combined symbol
        if 'iscombined' not in properties:
            primaryPartsOfSpeech[symbol] = properties
        else:
            # It is combined, so parse which symbols it's a combination of
            symbollist = symbol.split('^')
            combinedNumbers = []
            for lookup in symbollist:
                if lookup not in primaryPartsOfSpeech:
                    print("*** error: unable to find symbol " + lookup + " in combined symbol " + symbol)
                    exit(1)
                else:
                    combinedNumbers.append(primaryPartsOfSpeech[lookup]['mapval'])

            properties['values'] = combinedNumbers
            length = len(combinedNumbers)
            if length in combinations:
                combinations[length][mapValue] = combinedNumbers
            else:
                combinations[length] = { mapValue: combinedNumbers }


# check table
def checkSymbolTable(table):
    for i in propertyNames:
        propertyNames[i] = 0

    # Check each symbol, which contains a dictionary of properties
    for element in table.values():
        # Check this symbol's properties
        for key, value in element.items():
            if key not in propertyNames:
                print("*** error: invalid property name: " + key)
                exit(1)

            if key in propertyNames:
                propertyNames[key] = propertyNames[key] + 1


checkSymbolTable(partsOfSpeech)

# write out Phones pkb
def encodeProperties(dict):
    properties = 0
    for test, value in propertyValues.items():
        if test in dict:
            properties |= value
    return properties

# First write out the index of how many of each length there are
runningoffset = 32
for i in range(1, 9):
    # Offset starts at 32, then grows by how many the previous had
    if i == 1:
        offset = runningoffset
        howmany = len(primaryPartsOfSpeech)
    else:
        if i == 2:
            offset = runningoffset + howmany # Each single took 1 byte
        else:
            offset = runningoffset + howmany * i # Each multiple took 1+i which is what i is now

        if i in combinations:
            howmany = len(combinations.get(i))
        else:
            offset = 0
            howmany = 0

    if offset != 0:
        runningoffset = offset

    args.outfile.write(struct.pack('<H', howmany))
    args.outfile.write(struct.pack('<H', offset))

# Next write out parts of speech
for i in primaryPartsOfSpeech:
    args.outfile.write(struct.pack('<B', primaryPartsOfSpeech[i]['mapval']))

# Finally write out the combined symbols and what they are combinations of 
for i in range(2, 9):
    if i in combinations:
        symbolList = combinations[i]
        for symbol, values in symbolList.items():
            args.outfile.write(struct.pack('<B', symbol))
            for value in values:
                args.outfile.write(struct.pack('<B', value))

args.outfile.close()
