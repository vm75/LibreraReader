#!/usr/bin/env python3
"""Exercise the production image JNI bridge using MuPDF's bundled host archives."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mupdf', type=Path, default=ROOT.parent / 'mupdf')
    parser.add_argument('--libraries', type=Path, required=True,
                        help='MuPDF host OUT directory built with bundled codecs and PIC')
    parser.add_argument('--output', type=Path, default=ROOT / 'Builder/build/image-tests')
    args = parser.parse_args()
    args.mupdf = args.mupdf.resolve()
    args.libraries = args.libraries.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve()
    java_home = Path(shutil.which('javac')).resolve().parents[1]
    archives = [args.libraries / 'libmupdf.a', args.libraries / 'libmupdf-third.a']
    archives += [args.libraries / 'libjxl/lib' / name for name in (
        'libjxl_dec.a', 'libjxl_cms.a', 'libhwy.a', 'libbrotlidec.a', 'libbrotlicommon.a')]
    for archive in archives:
        if not archive.is_file():
            parser.error('Missing bundled host archive: ' + str(archive))
    run('cc', '-fPIC', '-I' + str(java_home / 'include'),
        '-I' + str(java_home / 'include/linux'), '-I' + str(args.mupdf / 'include'),
        '-c', ROOT / 'Builder/jni/mupdf-image.c', '-o', output / 'mupdf-image.o')
    run('c++', '-shared', '-o', output / 'libMuPDF.so', output / 'mupdf-image.o',
        *archives, '-Wl,--no-undefined', '-lpthread', '-ldl', '-lm')
    config = output / 'generated/com/foobnix/LibreraBuildConfig.java'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('package com.foobnix; public class LibreraBuildConfig {'
                      ' public static final String FLAVOR = System.getProperty("test.flavor", "fdroid"); }')
    classes = output / 'classes'
    classes.mkdir(exist_ok=True)
    run(java_home / 'bin/javac', '-d', classes, config,
        ROOT / 'app/src/main/java/com/foobnix/pdf/info/Engines.java',
        ROOT / 'app/src/main/java/org/ebookdroid/droids/mupdf/codec/MuPdfImage.java',
        ROOT / 'Builder/tests/NativeImageSmoke.java')
    assets = ROOT / 'app/src/androidTest/assets/native-images'
    run(java_home / 'bin/java', '-Djava.awt.headless=true', '-Djava.library.path=' + str(output),
        '-cp', classes, 'NativeImageSmoke', assets)
    # A missing native library proves that the production flavour guard runs first.
    run(java_home / 'bin/java', '-Djava.awt.headless=true', '-Dtest.flavor=fdroidJS',
        '-Djava.library.path=' + str(output / 'missing'), '-cp', classes, 'NativeImageSmoke', assets)


if __name__ == '__main__':
    main()
