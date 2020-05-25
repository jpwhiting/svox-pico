# Pico TTS

Text to speech voice synthesizer from SVox, included in Android AOSP.

Updated to improve building on linux and trying to fix licensing issues soon.
Lingware binary files are generated from pico_resources source text files, but
use binary windows only executables. Hopefully that can get remedied by creating
new sources for the tools.

## Build and install in Linux

Configure & build:

```
meson builddir
cd builddir
ninja
```

Install (this install files to /usr/bin, /usr/lib and /usr/share/pico):

```
ninja install
```

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
