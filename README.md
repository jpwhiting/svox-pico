# Pico TTS

Text to speech voice synthesizer from SVox, included in Android AOSP.

Updated to improve building on linux and trying to fix licensing issues soon.
Lingware binary files are generated from the pico_resources source text files in
`lingware/`. The Windows only executables of the original build chain are
replaced by Python reimplementations, see [Rebuilding the lingware](#rebuilding-the-lingware).

## Build and install in Linux

Configure & build:

```
meson setup --prefix=/usr builddir
cd builddir
ninja
```

Install (this install files to /usr/bin, /usr/include, /usr/lib and /usr/share/pico):

```
ninja install
```

Note: To build with debugging use:
```
meson setup --prefix=/usr -Dc_args=-DPICO_DEBUG builddir
```

## Rebuilding the lingware

The voice files in `lang/` are built from the sources in `lingware/` (text
analysis in `lingware/textana`, signal generation in `lingware/siggen`, the
lists of knowledge bases per file in `lingware/configs`). This needs Python 3
and Perl, nothing else:

```
cd lingware/tools
python3 buildall.py
```

`buildall.py` builds all languages: `buildpkb.py` compiles the sources into
knowledge bases (`lingware/pkb/<lang>/*.pkb`) and `buildbin.py` packs them into
`lang/*.bin`. One language and voice at a time:

```
python3 buildpkb.py en GB kh0
python3 buildbin.py en-GB kh0
```

The compilers of the original SVOX build chain, which were Windows executables,
are reimplemented in Python: `picoloadlex.py` (lexicon), `picoloadfst.py`
(finite state transducers), `dt2pkb.py` (decision trees) and `pdf2pkb.py`
(probability density functions). Their output is byte identical to the original
executables: all 198 knowledge bases of the six languages match the reference
`.pkb` files built by them, and so do the 18 `.bin` files.

`buildbin.py` names the files with their version, e.g.
`en-GB_ta_1.0.0.3-0-0.bin`; `--plain` gives the names `pico2wave` loads, e.g.
`en-GB_ta.bin`.

### Recovering sources from .bin files

`decompile.py` updates the sources of a voice from a `.bin` pair of another
version of it, e.g. the voices of `oldbinfiles/`:

```
cd lingware/tools
python3 decompile.py fr FR nk0 ../../oldbinfiles/fr-FR_ta.bin ../../oldbinfiles/fr-FR_nk0_sg.bin
```

It compares the knowledge bases built from the current sources with the ones
in the files and replaces the sources of those that differ by decompiled ones
(in place, comments are lost; names that the binary does not keep, such as the
symbols, the parts of speech and the automaton names, come from the current
sources). One decompiler per kind of knowledge base: `pkb2lex.py`,
`pkb2fst.py`, `pkb2dt.py`, `pkb2pdf.py`, `pkb2tpp.py`, `pkb2pos.py`;
`lwunpack.py` lists or extracts the knowledge bases of a `.bin` file.

Rebuilt, the text analysis files come out byte identical. The decision trees of
the signal generation can differ in the order of values in their tables (the
compiler orders them by the order of the tree nodes in the source, which the
binary does not keep), but they are the same trees and give the same speech.

## Libttspico api documentation

There's now automatically generated libttspico api documentation generated from main branch.

Find it here: https://jpwhiting.github.io/svox-pico/index.html

## Usage

```
pico2wave -l LANG -w OUT_WAV_FILE "text you want to synthesize"
paplay OUT_WAV_FILE
rm OUT_WAV_FILE
```

Languages can be: en-EN, en-GB, es-ES, de-DE, fr-FR, it-IT

Output file must be .wav

## License

License Apache-2.0 (see COPYING)
