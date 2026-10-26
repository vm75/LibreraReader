# Working on vm75/LibreraReader

This fork extends foobnix/LibreraReader with the vm75/MuPDF integration and WebP /
JPEG XL document, cover, and preview support. Read [FORK-README.md](FORK-README.md)
for the extension boundaries, native setup, and upstream maintenance workflow;
[README.md](README.md) contains the general Librera documentation.

## Repository map

- `app/src/main/java/org/ebookdroid/`: document routing and codec engines.
- `app/src/main/java/org/ebookdroid/droids/mupdf/codec/MuPdfImage.java` and
  `Builder/jni/mupdf-image.c`: production image JNI bridge.
- `app/src/main/java/com/`: `BaseExtractor.java`, `foobnix/sys/ImageExtractor.java`,
  and `foobnix/sys/JxlBitmapDecoder.java` handle previews and catalogue covers.
- `Builder/link_to_mupdf_fork.sh`, `Builder/jni/Android-fork.mk`: build directly
  from the configured vm75/mupdf checkout and reuse its bundled codecs.
- `Builder/jni/libmupdf_librera_fork.c`: Librera's document JNI adapter.
- `Builder/build-nomupdf.sh`, `Builder/jni/Android-nomupdf.mk`: auxiliary native
  library for JS variants, without MuPDF.
- `Builder/tests/`, `app/src/androidTest/assets/native-images/`: fork build and
  native image regressions and fixtures.
- `app/build.gradle`, `gradle/libs.versions.toml`: flavours, packaging, versions.
- `scripts/rebase-fork.py`, `scripts/test-rebase-fork.py`: upstream maintenance.

## Fork maintenance

- `origin` is `vm75/LibreraReader`; `upstream` is `foobnix/LibreraReader`.
  Keep fork commits on `main`, rebased above the chosen upstream base. Do not
  merge upstream into the fork stack or replace fork features with upstream.
- Use `python3 scripts/rebase-fork.py` from a clean, committed `main`.
  It defaults to the highest stable numeric upstream release tag; use
  `--base upstream/master` only when deliberately following development.
- When asked to update upstream, inspect the saved backup and range-diff,
  resolve conflicts against current upstream APIs, continue the rebase, and
  validate the result. A Git conflict is work to resolve, not a reason to stop.
  Do not blanket-select `ours` or `theirs`; inspect reused rerere resolutions.
- Keep maintenance, dependency updates, and functional changes in focused
  commits so the fork stack stays reviewable. Never discard uncommitted work
  or silently stash it to make an update run. Do not push automatically.
- The sibling MuPDF repository is independently maintained. Do not pull, rebase,
  or rewrite it as a side effect of updating Librera. Keep library APIs generic;
  Librera-specific adaptation belongs in this repository.

## Engineering constraints

- Use KISS and YAGNI. Search first; read task-relevant source and linked docs.
  Avoid broad reads of generated output, vendored libraries, or the wiki.
- Preserve unrelated changes, existing conventions, and JNI entry points.
- Native variants may advertise JXL; JS variants must not load MuPDF or
  advertise formats they cannot decode. Preserve Android WebP support there.
- Reuse MuPDF's pinned codec sources and Android modules; do not add a separate
  libjxl clone or copy a decoder into Librera. Preserve SDK refresh on rebuild,
  exact revision metadata, per-ABI packaging, and codec notices.
- Preserve image orientation, transparency, width limits, malformed-input
  handling, and JNI/Fitz cleanup. Verify both image previews and document paths.
- For string changes, follow [CLAUDE.md](CLAUDE.md): update every translation in
  the same change, preserve placeholders, and keep Hebrew resource aliases equal.
- Keep signing keys, service credentials, local paths, and generated binaries
  out of commits. Do not run release/publication scripts as routine validation.

## Validation

```sh
python3 scripts/test-rebase-fork.py
python3 Builder/tests/test_fork_build.py
bash -n Builder/link_to_mupdf_fork.sh Builder/build-nomupdf.sh Builder/all-release.sh Builder/build-librera-beta.sh
```

With the Android SDK, NDK, and user Gradle properties configured as described
in [the fork guide](FORK-README.md#build-and-validate):

```sh
Builder/build-nomupdf.sh fork
./gradlew :app:assembleFdroidDebug :app:assembleFdroidJSDebug
./gradlew :app:testFdroidDebugUnitTest
```

Use the host image JNI checks in the fork guide when changing codecs, image
routing, native build flags, or the JNI adapter. Run appropriate device tests
when a device is available. The rebase helper's automatic checks are lightweight;
they do not replace APK builds or pixel-level decoding tests.

## Completion and documentation

Validate affected behaviour before finishing; report failed or unrun checks
accurately. Review changes for scope, generated files, and credentials.
Update `FORK-README.md` when extensions, setup, or the rebase workflow change;
update this file when navigation, commands, or maintenance rules change.
Keep general upstream documentation intact where possible and link fork details
from `README.md` rather than duplicating them there.
