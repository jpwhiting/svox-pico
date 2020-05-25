## meson.build. Build file for building svox-pico and test executable

project(
  'svox-pico', 'c',
  version: '1.0',
  default_options: [
    'c_std=c99',
    'warning_level=2'
  ],
)

api_major = '1'
abi_major = '1'
abi_minor = '20200522'

pkg = import('pkgconfig')

project_include_dirs = include_directories('lib/')

c_compiler = meson.get_compiler('c')

math = c_compiler.find_library('m')

popt = dependency(
    'popt'
)

bin_rpath = '${ORIGIN}/../'

subdir('lib')
subdir('bin')

