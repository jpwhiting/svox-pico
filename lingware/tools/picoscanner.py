#!/usr/bin/env python3
# picoscanner.py --- common tokenizer for SVOX Pico lingware source files
#
# Implements the lexical conventions described in SVOX_Pico_Lingware.pdf:
#  - line comments start with '!' and extend to the end of the line
#  - range comments are enclosed in '[' ... ']' and may be nested
#  - strings are delimited by "..." or '...'; a delimiter inside the string
#    is written doubled ("""" is the string consisting of one '"')
#  - keywords start with ':' (e.g. :SYM, :PROP, :ALPHABET)
#  - identifiers, (signed) integers and single punctuation characters
#
# Licensed under the Apache License, Version 2.0

import sys

STR = 'str'
ID = 'id'
INT = 'int'
KW = 'kw'
PUNCT = 'punct'
EOF = 'eof'


class ScanError(Exception):
    pass


class Token:
    __slots__ = ('kind', 'value', 'line', 'quote')

    def __init__(self, kind, value, line, quote=None):
        self.kind = kind
        self.value = value
        self.line = line
        self.quote = quote

    def __repr__(self):
        return 'Token(%s,%r,%d)' % (self.kind, self.value, self.line)


def _is_id_start(c):
    return c.isalpha() or c == '_'


def _is_id_char(c):
    return c.isalnum() or c in '_'


def tokenize(text, filename='<input>', range_comments=True, id_chars=''):
    """Return list of tokens of text.

    id_chars: additional characters allowed inside identifiers (e.g. '^').
    """
    toks = []
    i = 0
    n = len(text)
    line = 1
    while i < n:
        c = text[i]
        if c == '\n':
            line += 1
            i += 1
        elif c.isspace() or c == '﻿':
            i += 1
        elif c == '!':
            while i < n and text[i] != '\n':
                i += 1
        elif c == '[' and range_comments:
            depth = 1
            start = line
            i += 1
            while i < n and depth > 0:
                if text[i] == '[':
                    depth += 1
                elif text[i] == ']':
                    depth -= 1
                elif text[i] == '\n':
                    line += 1
                i += 1
            if depth > 0:
                raise ScanError('%s: open comment at end of file; started on line %d'
                                % (filename, start))
        elif c == '"' or c == "'":
            q = c
            i += 1
            buf = []
            start = line
            while True:
                if i >= n:
                    raise ScanError('%s(%d): unterminated string' % (filename, start))
                ch = text[i]
                if ch == q:
                    if i + 1 < n and text[i + 1] == q:
                        buf.append(q)
                        i += 2
                        continue
                    i += 1
                    break
                if ch == '\n':
                    line += 1
                buf.append(ch)
                i += 1
            toks.append(Token(STR, ''.join(buf), start, q))
        elif c == ':' and i + 1 < n and _is_id_start(text[i + 1]):
            j = i + 1
            while j < n and _is_id_char(text[j]):
                j += 1
            toks.append(Token(KW, text[i + 1:j].upper(), line))
            i = j
        elif c.isdigit() or (c in '+-' and i + 1 < n and text[i + 1].isdigit()):
            j = i + 1
            while j < n and text[j].isdigit():
                j += 1
            toks.append(Token(INT, int(text[i:j]), line))
            i = j
        elif _is_id_start(c):
            j = i + 1
            while j < n and (_is_id_char(text[j]) or text[j] in id_chars):
                j += 1
            toks.append(Token(ID, text[i:j], line))
            i = j
        else:
            toks.append(Token(PUNCT, c, line))
            i += 1
    toks.append(Token(EOF, None, line))
    return toks


class Parser:
    """Small recursive-descent helper over a token list."""

    def __init__(self, toks, filename='<input>'):
        self.toks = toks
        self.pos = 0
        self.filename = filename

    @property
    def tok(self):
        return self.toks[self.pos]

    def peek(self, k=1):
        return self.toks[min(self.pos + k, len(self.toks) - 1)]

    def next(self):
        t = self.toks[self.pos]
        if t.kind != EOF:
            self.pos += 1
        return t

    def error(self, msg, tok=None):
        tok = tok or self.tok
        raise ScanError('*** error in %s(%d) : %s' % (self.filename, tok.line, msg))

    def at(self, kind, value=None):
        t = self.tok
        return t.kind == kind and (value is None or t.value == value)

    def accept(self, kind, value=None):
        if self.at(kind, value):
            return self.next()
        return None

    def expect(self, kind, value=None, what=None):
        if self.at(kind, value):
            return self.next()
        self.error((what or ('%s %s' % (kind, value if value is not None else ''))).strip()
                   + ' expected')


def read_text(path):
    with open(path, 'rb') as f:
        data = f.read()
    if data.startswith(b'\xef\xbb\xbf'):
        data = data[3:]
    return data.decode('utf-8')


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)
