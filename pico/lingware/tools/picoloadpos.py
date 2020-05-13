#!/usr/bin/env python3
# python script picoloadpos.py --- creates pkb containing pos table.
#
# Copyright 2020 Jeremy Whiting <jpwhiting@kde.org>
#
# load pico pos src file and create pos pkb file
#
# accepted syntax:
# - parses line of the following format:
#   :SYM "<sym>" :PROP mapval = <uint8> { , <propname> = <int> }
# - initial '!' and trailing '!.*' are treated as comments, no '[]'

import argparse
import os
import re
import struct

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
# table with symbol name keys used to do lookup of combined symbols
partsOfSpeech = {}

# table with symbol name number keys (specified with property mapval)
# combined symbols also contain a list of symbols they are a combination of
symbolNumbers = {}

# table of combined symbols key is how many symbols were combined (2-8)
# single parts of speech are in partsOfSpeech, 2-8 symbol combinations are
# here
combinations = {}

# array of symbol name numer keys used (to check for unique mapvals)
symbolUsed = {}

# Comment regular expression
commentLine = re.compile('^\\s*!.*$')
# Double quote SYM definition
doubleSYM = re.compile(':SYM\\s+"([^"]+)"\\s+(.*)')
# Single quote SYM definition
singleSYM = re.compile(":SYM\\s+'([^']+)'\\s+(.*)")
# Properties regular expression
propertiesLine = re.compile("^:PROP\\s+mapval\\s*=\\s*(\\d+)\\s*,*(.*)")

# parse input file, build up syms and symnrs tables
line = args.infile.readline()
while line:
    #  if string.match(line, "^%s*!.*$") or string.match(line, "^%s*$") then
    #    -- discard comment-only lines
    if commentLine.match(line):
        line = args.infile.readline()
        continue

    #    -- Remove whitespace
    line = line.strip()
    symbol = None
    rest = None

    m = doubleSYM.match(line)
    if m:
        symbol = m.group(1)
        rest = m.group(2)
    else:
        m = singleSYM.match(line)
        if m:
            symbol = m.group(1)
            rest = m.group(2)

    if symbol and rest:

        m = propertiesLine.match(rest)
        mappedValue = int(m.group(1))

        otherProperties = None

        if len(m.groups()) > 1:
            otherProperties = m.group(2).strip()

        if mappedValue:
            properties = {'mapval': mappedValue}

            if otherProperties:
                # Parse otherProperties setting flags as appropriate
                otherPropList = otherProperties.split(',')
                for property in otherPropList:
                    words = property.split('=')
                    key = words[0].strip()
                    value = words[1].strip()
                    if not value == '1':
                        print("*** error in property list, optional properties"
                              " only accept \"1\": " + property)
                        continue

                    properties[key] = value
            else:
                pass

            # Make sure this value isn't used yet
            if mappedValue in symbolUsed:
                print("*** error: mapval values must be unique, " +
                      str(mappedValue))
            else:
                symbolUsed[mappedValue] = True

            # Only add to partsOfSpeech list if it's not a combined symbol
            if 'iscombined' not in properties:
                partsOfSpeech[symbol] = properties
            else:
                # It is combined, so parse which symbols it's a combination of
                symbollist = symbol.split('^')
                combinedNumbers = []
                for lookup in symbollist:
                    if lookup not in partsOfSpeech:
                        print("*** error: unable to find symbol " + lookup + " in combined symbol " + symbol)
                        exit(1)
                    else:
                        combinedNumbers.append(partsOfSpeech[lookup]['mapval'])

                properties['values'] = combinedNumbers
                length = len(combinedNumbers)
                if length in combinations:
                    combinations[length][mappedValue] = combinedNumbers
                else:
                    combinations[length] = { mappedValue: combinedNumbers }

            symbolNumbers[mappedValue] = properties

    line = args.infile.readline()


args.infile.close()


# check symbolNumbers
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


checkSymbolTable(symbolNumbers)

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
        howmany = len(partsOfSpeech)
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
for i in partsOfSpeech:
    args.outfile.write(struct.pack('<B', partsOfSpeech[i]['mapval']))

# Finally write out the combined symbols and what they are combinations of 
for i in range(2, 9):
    if i in combinations:
        symbolList = combinations[i]
        for symbol, values in symbolList.items():
            args.outfile.write(struct.pack('<B', symbol))
            for value in values:
                args.outfile.write(struct.pack('<B', value))

args.outfile.close()
