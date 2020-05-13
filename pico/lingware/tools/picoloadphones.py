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
import re

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
syms = {}
# table with symbol name number keys (specified with property mapval)
symbolNumbers = {}
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

            symbolNumbers[mappedValue] = properties

    line = args.infile.readline()


args.infile.close()


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
            specialIDs[value] = element['mapval']

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
