
ttspico_sources = [
    'picoacph.c',
    'picoapi.c',
    'picobase.c',
    'picocep.c',
    'picoctrl.c',
    'picodata.c',
    'picodbg.c',
    'picoextapi.c',
    'picofftsg.c',
    'picokdbg.c',
    'picokdt.c',
    'picokfst.c',
    'picoklex.c',
    'picoknow.c',
    'picokpdf.c',
    'picokpr.c',
    'picoktab.c',
    'picoos.c',
    'picopal.c',
    'picopam.c',
    'picopr.c',
    'picorsrc.c',
    'picosa.c',
    'picosig.c',
    'picosig2.c',
    'picospho.c',
    'picotok.c',
    'picotrns.c',
    'picowa.c'
]

ttspico_public_headers = [
    'picoacph.h',
    'picoapid.h',
    'picoapi.h',
    'picobase.h',
    'picocep.h',
    'picoctrl.h',
    'picodata.h',
    'picodbg.h',
    'picodefs.h',
    'picodsp.h',
    'picoextapi.h',
    'picofftsg.h',
    'picokdbg.h',
    'picokdt.h',
    'picokfst.h',
    'picoklex.h',
    'picoknow.h',
    'picokpdf.h',
    'picokpr.h',
    'picoktab.h',
    'picoos.h',
    'picopal.h',
    'picopam.h',
    'picopltf.h',
    'picopr.h',
    'picorsrc.h',
    'picosa.h',
    'picosig2.h',
    'picosig.h',
    'picospho.h',
    'picotok.h',
    'picotrns.h',
    'picowa.h'
]

install_headers(
    ttspico_public_headers,
    subdir: 'pico'
)

ttspico = library(
    'ttspico',
    ttspico_sources + ttspico_public_headers,
    dependencies: [math],
    soversion: abi_major,
    version: abi_major + '.' + abi_minor,
    install: true
)

pkg.generate(
    description: 'svox pico tts library',
    libraries: [ttspico],
    name: 'ttspico' + abi_major,
    subdirs: 'pico',
    version: meson.project_version(),
    variables: 'datadir=${prefix}/share/pico/lang'
)

ttspico_dep = declare_dependency(
    include_directories: project_include_dirs,
    link_with: ttspico,
    sources: ttspico_public_headers
)

