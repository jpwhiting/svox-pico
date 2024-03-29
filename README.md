# Pico TTS

Text to speech voice synthesizer from SVox, included in Android AOSP.

Updated to improve building on linux and trying to fix licensing issues soon.
Lingware binary files are generated from pico_resources source text files, but
use binary windows only executables. Hopefully that can get remedied by creating
new sources for the tools.

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
