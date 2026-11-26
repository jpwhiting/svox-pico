#!/usr/bin/env python3
# Build all lingware files for all languages
# by running buildpkb and buildbin scripts.

import glob
import os
import subprocess
import sys

pkbfiles = glob.glob('../pkb/*/*.pkb')

for filename in pkbfiles:
    os.remove(filename)

print('Building de-DE lingware', flush=True)
subprocess.run([sys.executable, './buildpkb.py', 'de', 'DE', 'gl0'])
subprocess.run([sys.executable, './buildbin.py', 'de-DE', 'gl0'])

print('Building en-GB lingware', flush=True)
subprocess.run([sys.executable, './buildpkb.py', 'en', 'GB', 'kh0'])
subprocess.run([sys.executable, './buildbin.py', 'en-GB', 'kh0'])

print('Building en-US lingware', flush=True)
subprocess.run([sys.executable, './buildpkb.py', 'en', 'US', 'lh0'])
subprocess.run([sys.executable, './buildbin.py', 'en-US', 'lh0'])

print('Building es-ES lingware', flush=True)
subprocess.run([sys.executable, './buildpkb.py', 'es', 'ES', 'zl0'])
subprocess.run([sys.executable, './buildbin.py', 'es-ES', 'zl0'])

print('Building fr-FR lingware', flush=True)
subprocess.run([sys.executable, './buildpkb.py', 'fr', 'FR', 'nk0'])
subprocess.run([sys.executable, './buildbin.py', 'fr-FR', 'nk0'])

print('Building it-IT lingware', flush=True)
subprocess.run([sys.executable, './buildpkb.py', 'it', 'IT', 'cm0'])
subprocess.run([sys.executable, './buildbin.py', 'it-IT', 'cm0'])

