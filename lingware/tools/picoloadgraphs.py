#!/usr/bin/env python3
# python script picoloadgraphs.py --- creates pkb containing graphs table.
#
# Copyright 2020 Jeremy Whiting <jpwhiting@kde.org>
#
# load pico graphs src file and create graphs pkb file
#
# accepted syntax:
# - parses line of the following format:
#   :SYM "<sym>" :PROP mapval = <uint8> { , <propname> = <int> }
# - initial '!' and trailing '!.*' are treated as comments, no '[]'

import argparse
import os
import struct

import symboltable

# init
args = argparse.Namespace()

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('infile', type=argparse.FileType('r', encoding='UTF-8'),
                    help='source file name of graphs text data')
parser.add_argument('outfile', type=argparse.FileType('wb'),
                    help='destination file name of graphs binary data')

parser.parse_args(namespace=args)

if not args.infile:
    print("*** error: could not open input file: " + args.infile)
    exit(1)

if not args.outfile:
    print("*** error: could not open output file: " + args.outfile)
    exit(1)

table = symboltable.SymbolTable()
symbols = table.parseFile(args.infile)
args.infile.close()

# Resulting graphs end up here as we go through the symbols
graphs = []

# Sort the symbols to create from/to groups of like items
lastProperties = {}
lastSymbol = 0
for symbol in sorted(symbols.keys()):
    properties = symbols[symbol]
    # print("Checking symbol: " + symbol + " with properties: ")
    # print(properties)

    # print("Last properties: ")
    # print(lastProperties)

    # print("Last symbol: " + str(lastSymbol))

    if properties == lastProperties and ord(symbol) - 1 == lastSymbol:
        # Begin a group or add this item to the previous group
        # print("Properties match previous symbol, so adding this to the previous item")
        graphs[len(graphs) - 1]['to'] = symbol

    else:
        propertiescopy = properties.copy()
        propertiescopy['from'] = symbol
        graphs.append(propertiescopy)

    lastSymbol = ord(symbol)
    lastProperties = properties

# print("graphs: ")
# print(graphs)
# print("Length: " + str(len(graphs)))

def graphBytes(properties):
    result = bytearray()
    # Return the bytes for the given graph object to be written to file
    # First write the propset, which is which properties follow the character as follows:
    # Note: From picoktab.c
    # TO           01
    # TOKENTYPE    02
    # TOKENSUBTYPE 04
    # VALUE        08
    # LOWERCASE    10
    # GRAPHSUBS1   20
    # GRAPHSUBS2   40
    # PUNCT        80

    propset = 2 # All graphs have a token type
    if 'to' in properties:
        propset |= 1
    if 'lowercase' in properties:
        propset |= 0x10
    if 'graphsubs1' in properties:
        propset |= 0x20
    if 'graphsubs2' in properties:
        propset |= 0x40
    if 'punct' in properties:
        propset |= 0x80

    result.append(propset)

    # 'stoken' property, all are mutualy exclusive
    #   1 'vowel-like' letter (part of letter simple token       -> V)
    #   2 'consonant-like' letter (part of letter simple token   -> L)
    #   3 digit (part of digit simple token                      -> D)
    #   4 non-L/non-D (part of sequence simple token             -> S)
    #   5 non-L/non-D (part of single char simple token          -> C)

    tokenTypes = {
        0: "W",
        1: "V",
        2: "L",
        3: "D",
        4: "S",
        5: "C"
    }
    tokentype = tokenTypes.get(int(properties['stoken']))

    # graph = PROPSET FROM TO [TOKENTYPE] [TOKENSUBTYPE] 
    #   [VALUE] [LOWERCASE] [GRAPHSUBS1] [GRAPHSUBS2] [PUNCT]

    # propset first
    print("propset: " + hex(propset))
    # then the symbol
    print("from: " + hex(ord(properties['from'])))
    result.extend(properties['from'].encode('utf-8'))
    # then if set, punctuation
    if 'to' in properties:
        print("to: " + hex(ord(properties['to'])))
        result.extend(properties['to'].encode('utf-8'))
    print("tokenType: " + tokentype)
    result.extend(tokentype.encode('utf-8'))
    if 'tokensubtype' in properties: # Not sure what this would be in source files...
        print("tokensubtype: " + properties['tokensubtype'])
        result.extend(tokensubtype.encode('utf-8'))
    if 'value' in properties: # Also not sure about this one
        print("value: " + properties['value'])
        result.extend(bytes([ord(properties['value'])]))
    if 'lowercase' in properties:
        print("lowercase: " + properties['lowercase'])
        result.extend(bytes([ord(properties['lowercase'])]))
    if 'graphsubs1' in properties:
        print("graphsubs1: " + properties['graphsubs1'])
        result.extend(bytes([ord(properties['graphsubs1'])]))
    if 'graphsubs2' in properties:
        print("graphsubs2: " + properties['graphsubs2'])
        result.extend(bytes([ord(properties['graphsubs2'])]))
    if 'punct' in properties:
        print("punct: " + str(properties['punct']))
        result.extend(bytes([int(properties['punct'])])) # 1 or 2
    
    return result

nextoffset = 0
offsets = []
graphdata = bytearray()

# Dump graph data to graphdata, keeping the offsets from 0 in offsets
# Now that we have our graphs serialize them to bytes, then write their offsets followed
for graph in graphs:
    data = graphBytes(graph)
    offsets.append(nextoffset)
    nextoffset += len(data)
    graphdata.extend(data)

offsetsize = 2
offsetformat = '<H'
datasize = len(graphdata) + (2 * len(graphs)) + 3

if datasize > 65536:
    print("datasize is: " + str(datasize))
    offsetsize = 3
    offestformat = '<H' # Need a solution for this 3 byte offset format...
    datasize = len(graphdata) + (3 * len(graphs)) + 3

if datasize > 16777216:
    offsetsize = 4
    offsetformat = '<I'
    datasize = len(graphdata) + (4 * len(graphs)) + 3

offsetslength = 3 + (offsetsize * len(graphs))

# Write how many graphs we have in 2 bytes
args.outfile.write(struct.pack('<H', len(graphs)))
# Write how many bytes each offset is in one byte
args.outfile.write(struct.pack('<B', offsetsize))

# Now dump the offsets
for off in offsets:
    args.outfile.write(struct.pack(offsetformat, off + offsetslength))

# Now dump the graphs themselves
args.outfile.write(graphdata)

# by the data to args.outfile
args.outfile.close()

