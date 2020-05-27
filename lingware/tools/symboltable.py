#!/usr/bin/env python3
# python script symboltable.py --- Parses symbol table utf source files.
#
# Copyright 2020 Jeremy Whiting <jpwhiting@kde.org>
#
# Load symbol table utf file into dictionary of symbols.
# Used for loading parts of speech, phones, and graphs source files.
# See SVOX_Pico_Lingware.pdf chapter 4 for syntax and descriptions.
#
# accepted syntax:
# - parses line of the following format:
#   :SYM "<sym>" :PROP mapval = <uint8> { , <propname> = <int> }
# - initial '!' and trailing '!.*' are treated as comments, no '[]'

import json
import re

class SymbolTable:
    def __init__(self):
        # Comment regular expression
        self.commentLine = re.compile('^\\s*!.*$')
        # Double quote SYM definition
        self.doubleSYM = re.compile(':SYM\\s+"([^"]+)"\\s+(.*)')
        # Single quote SYM definition
        self.singleSYM = re.compile(":SYM\\s+'([^']+)'\\s+(.*)")
        # Properties regular expression
        self.propertiesLine = re.compile("^:PROP\\s+(.*)")


    def parseFile(self, infile):
        results = {}

        # parse input file, build up syms and symnrs tables
        line = infile.readline()
        while line:
            #  if string.match(line, "^%s*!.*$") or string.match(line, "^%s*$") then
            #    -- discard comment-only lines
            if self.commentLine.match(line):
                line = infile.readline()
                continue

            #    -- Remove whitespace
            line = line.strip()
            symbol = None
            rest = None
            properties = {}

            m = self.doubleSYM.match(line)
            if m:
                symbol = m.group(1)
                rest = m.group(2)
            else:
                m = self.singleSYM.match(line)
                if m:
                    symbol = m.group(1)
                    rest = m.group(2)

            if symbol and rest:
                otherProperties = None
                m = self.propertiesLine.match(rest)
                otherProperties = m.group(1).strip()
                print("Parsing symbol: " + symbol + " properties: " + otherProperties)

                if otherProperties:
                    # Parse otherProperties setting flags as appropriate
                    otherPropList = otherProperties.split(',')
                    for property in otherPropList:
                        words = property.split('=')
                        key = words[0].strip()
                        # Use json.loads to remove "" around strings
                        value = json.loads(words[1].strip())
#                        print("Property: " + key + " value: " + value)
                        properties[key] = value
                else:
                    pass

                results[symbol] = properties
    
            line = infile.readline()
        return results

