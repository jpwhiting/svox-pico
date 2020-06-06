#!/usr/bin/env python3
# Build all lingware files for all languages
# by running buildpkb and buildbin scripts.

import glob
import os
import subprocess

pkbfiles = glob.glob('../pkb/*/*.pkb')

# for filename in pkbfiles:
#    os.remove(filename)

# ./buildpkb.sh de DE gl0
# ./buildpkb.sh en GB kh0
# ./buildpkb.sh en US lh0
# ./buildpkb.sh es ES zl0
# ./buildpkb.sh fr FR nk0
# ./buildpkb.sh it IT cm0

subprocess.run(['python', './buildbin.py', 'de-DE', 'gl0'])
subprocess.run(['python', './buildbin.py', 'en-GB', 'kh0'])
subprocess.run(['python', './buildbin.py', 'en-US', 'lh0'])
subprocess.run(['python', './buildbin.py', 'es-ES', 'zl0'])
subprocess.run(['python', './buildbin.py', 'fr-FR', 'nk0'])
subprocess.run(['python', './buildbin.py', 'it-IT', 'cm0'])
