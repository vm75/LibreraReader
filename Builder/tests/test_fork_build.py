#!/usr/bin/env python3
"""Check bundled codec orchestration without downloading or compiling codecs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'link_to_mupdf_fork.sh'


class ForkBuildTest(unittest.TestCase):
    def test_pinned_source_is_refreshed_on_every_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            builder = root / 'reader/Builder'
            builder.mkdir(parents=True)
            shutil.copyfile(SCRIPT, builder / SCRIPT.name)
            mupdf = root / 'mupdf'
            (mupdf / '.git').mkdir(parents=True)
            (mupdf / 'scripts').mkdir()
            (mupdf / 'include/mupdf/fitz').mkdir(parents=True)
            (mupdf / 'include/mupdf/fitz/context.h').write_text('fz_set_reflow_options')
            (mupdf / 'include/mupdf/fitz/version.h').write_text('#define FZ_VERSION "1.29.0"')
            (mupdf / 'thirdparty/libjxl').mkdir(parents=True)
            (mupdf / 'thirdparty/libwebp').mkdir()
            (mupdf / 'thirdparty/libwebp/COPYING').write_text('WebP notice')
            (mupdf / 'scripts/build-android-jxl.py').write_text('''
import os, pathlib, sys
args = sys.argv[1:]
assert '--source' not in args, 'Use the helper default: MuPDF bundled libjxl'
assert pathlib.Path(os.environ['TEST_DEPENDENCIES']).exists(), 'Initialize dependencies first'
with open(os.environ['TEST_HELPER_LOG'], 'a') as log:
    log.write('build\\n')
out = pathlib.Path(args[args.index('--output') + 1]) / 'arm64-v8a'
(out / 'licenses').mkdir(parents=True, exist_ok=True)
(out / 'licenses/libjxl.txt').write_text('JXL notice')
''')
            commands = root / 'bin'
            commands.mkdir()

            def executable(name, code):
                target = commands / name
                target.write_text('#!/usr/bin/env python3\n' + code)
                target.chmod(0o755)

            executable('git', '''import os, pathlib, sys
args = sys.argv[1:]
if 'clone' in args:
    raise SystemExit('Must not clone an external codec')
if 'submodule' in args:
    with open(os.environ['TEST_GIT_LOG'], 'a') as log:
        log.write(' '.join(args) + '\\n')
    if 'third_party/skcms' in args:
        pathlib.Path(os.environ['TEST_DEPENDENCIES']).touch()
elif 'rev-parse' in args:
    print('test-pinned-revision')
''')
            executable('make', 'pass\n')
            executable('ndk-build', '''import pathlib, sys
out = pathlib.Path(next(a.split('=', 1)[1] for a in sys.argv if a.startswith('NDK_LIBS_OUT=')))
(out / 'arm64-v8a').mkdir(parents=True, exist_ok=True)
for library in ('libMuPDF.so', 'liblame.so'):
    (out / 'arm64-v8a' / library).write_bytes(b'library')
''')
            environment = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ['PATH'],
                LIBRERA_MUPDF_DIR=str(mupdf), LIBRERA_NDK_DIR=str(commands),
                LIBRERA_ABIS='arm64-v8a', GRADLE_USER_HOME=str(root / 'gradle'),
                TEST_DEPENDENCIES=str(root / 'initialized'),
                TEST_GIT_LOG=str(root / 'git.log'), TEST_HELPER_LOG=str(root / 'helper.log'))
            environment.pop('LIBRERA_JXL_SDK_DIR', None)
            for _ in range(2):
                subprocess.run(['bash', builder / SCRIPT.name], env=environment,
                               check=True, stdout=subprocess.DEVNULL)
            self.assertEqual((root / 'helper.log').read_text().splitlines(), ['build', 'build'])
            git_calls = (root / 'git.log').read_text()
            self.assertIn('third_party/brotli third_party/highway third_party/skcms', git_calls)
            self.assertNotIn('--recursive', git_calls)
            metadata = json.loads((builder / 'build/mupdf-fork/build.json').read_text())
            self.assertEqual(metadata['codecs'], dict.fromkeys(('libwebp', 'libjxl'), 'test-pinned-revision'))
            self.assertEqual((root / 'reader/app/src/main/assets/native-codecs/libjxl.txt').read_text(), 'JXL notice')


if __name__ == '__main__':
    unittest.main()
