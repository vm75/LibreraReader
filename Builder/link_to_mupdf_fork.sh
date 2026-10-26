#!/usr/bin/env bash
# Build directly from the sibling vm75/mupdf checkout, preserving its worktree.
set -euo pipefail
BUILD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)"
ROOT_DIR="$(dirname "$BUILD_DIR")"
GRADLE_PROPERTIES="${GRADLE_USER_HOME:-$HOME/.gradle}/gradle.properties"

property() {
    if [[ -f "$GRADLE_PROPERTIES" ]]; then
        sed -n "s/^$1=//p" "$GRADLE_PROPERTIES" | tail -n 1
    fi
}

MUPDF_ROOT="${LIBRERA_MUPDF_DIR:-$(property librera_mupdf_dir)}"
MUPDF_ROOT="${MUPDF_ROOT:-$(dirname "$ROOT_DIR")/mupdf}"
if [[ ! -d "$MUPDF_ROOT/.git" && ! -f "$MUPDF_ROOT/.git" ]]; then
    git clone --branch main git@github.com:vm75/mupdf.git "$MUPDF_ROOT"
fi
MUPDF_ROOT="$(cd "$MUPDF_ROOT" >/dev/null && pwd)"
if [[ ! -f "$MUPDF_ROOT/scripts/build-android-jxl.py" ]] ||
   ! grep -q fz_set_reflow_options "$MUPDF_ROOT/include/mupdf/fitz/context.h"; then
    echo "MuPDF checkout needs the fork's Android codecs and document options: $MUPDF_ROOT" >&2
    exit 1
fi

NDK_DIR="${LIBRERA_NDK_DIR:-${ANDROID_NDK_HOME:-$(property librera_ndk_dir)}}"
if [[ "${1:-}" == fdroid ]]; then
    NDK_DIR="${LIBRERA_FDROID_NDK_DIR:-$(property librera_fdroid_ndk_dir)}"
    NDK_DIR="${NDK_DIR:-${LIBRERA_NDK_DIR:-${ANDROID_NDK_HOME:-$(property librera_ndk_dir)}}}"
fi
if [[ ! -x "$NDK_DIR/ndk-build" ]]; then
    echo "Set ANDROID_NDK_HOME, LIBRERA_NDK_DIR, or librera_ndk_dir in $GRADLE_PROPERTIES" >&2
    exit 1
fi

read -r -a ABIS <<< "${LIBRERA_ABIS:-armeabi-v7a arm64-v8a x86 x86_64}"
JOBS="${LIBRERA_NATIVE_JOBS:-4}"
OUTPUT="$BUILD_DIR/build/mupdf-fork"

# Resolve Artifex's relative URLs against Artifex, then initialize only the
# decoder dependencies of the libjxl revision pinned by this MuPDF checkout.
git -C "$MUPDF_ROOT" -c remote.upstream.url=https://github.com/ArtifexSoftware/mupdf.git \
    -c branch.main.remote=upstream submodule update --init
git -C "$MUPDF_ROOT/thirdparty/libjxl" submodule update --init \
    third_party/brotli third_party/highway third_party/skcms

JXL_SDK="${LIBRERA_JXL_SDK_DIR:-$(property librera_jxl_sdk_dir)}"
JXL_SDK="${JXL_SDK:-$OUTPUT/jxl}"
# Let CMake check source dependencies every time. Testing only for an existing
# archive would retain an old SDK after MuPDF updates its bundled codec pins.
python3 "$MUPDF_ROOT/scripts/build-android-jxl.py" \
    --ndk "$NDK_DIR" --output "$JXL_SDK" --api 24 --jobs "$JOBS" --abis "${ABIS[@]}"

make -C "$MUPDF_ROOT" generate

"$NDK_DIR/ndk-build" -j"$JOBS" NDK_PROJECT_PATH="$ROOT_DIR" \
    APP_BUILD_SCRIPT="$BUILD_DIR/jni/Android-fork.mk" \
    NDK_APPLICATION_MK="$BUILD_DIR/jni/Application.mk" \
    APP_PLATFORM=android-24 "APP_ABI=${ABIS[*]}" \
    LIBRERA_MUPDF_ROOT="$MUPDF_ROOT" MUPDF_JXL_ROOT="$JXL_SDK" \
    NDK_OUT="$OUTPUT/obj" NDK_LIBS_OUT="$OUTPUT/libs"

# Publish outputs only after every requested ABI has built successfully.
mkdir -p "$ROOT_DIR/app/src/main/jniLibs"
for ABI in "${ABIS[@]}"; do
    mkdir -p "$ROOT_DIR/app/src/main/jniLibs/$ABI"
    cp "$OUTPUT/libs/$ABI/libMuPDF.so" "$ROOT_DIR/app/src/main/jniLibs/$ABI/"
    cp "$OUTPUT/libs/$ABI/liblame.so" "$ROOT_DIR/app/src/main/jniLibs/$ABI/"
done
# Keep packaged notices aligned with the codec sources used for this build.
NOTICES="$ROOT_DIR/app/src/main/assets/native-codecs"
mkdir -p "$NOTICES"
cp "$JXL_SDK/${ABIS[0]}/licenses/"*.txt "$NOTICES/"
cp "$MUPDF_ROOT/thirdparty/libwebp/COPYING" "$NOTICES/libwebp.txt"
python3 - "$MUPDF_ROOT" "$OUTPUT/build.json" <<'PY'
import json, pathlib, re, subprocess, sys
source = pathlib.Path(sys.argv[1])
version = re.search(r'#define FZ_VERSION "([^"]+)"',
                    (source / 'include/mupdf/fitz/version.h').read_text()).group(1)
revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
dirty = bool(subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True))
codecs = {name: subprocess.check_output(['git', '-C', str(source), 'rev-parse',
    'HEAD:thirdparty/' + name], text=True).strip() for name in ('libwebp', 'libjxl')}
pathlib.Path(sys.argv[2]).write_text(json.dumps({'version': version, 'revision': revision,
    'dirty': dirty, 'codecs': codecs, 'repository': 'git@github.com:vm75/mupdf.git'}, indent=2) + '\n')
PY
echo "Native libraries: $OUTPUT/libs"
