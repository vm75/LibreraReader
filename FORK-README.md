# vm75/LibreraReader extensions

This fork of [foobnix/LibreraReader](https://github.com/foobnix/LibreraReader)
uses [vm75/mupdf](https://github.com/vm75/mupdf) for native rendering, including
WebP and JPEG XL input. Fork commits are maintained on `main`, replayed on top
of upstream releases. See [README.md](README.md) for general Librera information
and [AGENTS.md](AGENTS.md) for contributor and coding-agent guidance.

## Extensions and boundaries

| Extension | Implementation and behaviour |
| --- | --- |
| MuPDF fork integration | `Builder/link_to_mupdf_fork.sh` builds the configured checkout directly. `Builder/jni/Android-fork.mk` reuses MuPDF's static JNI dependency modules instead of copying or patching library source. |
| WebP and JXL documents | Native document routing and file/MIME registration support standalone images; the MuPDF fork handles embedded images and CBZ input. |
| JXL covers and previews | `MuPdfImage.java` / `mupdf-image.c` convert encoded images to PNG for Android. Extractor and Glide integration cover local, archive, and catalogue image paths. Transparency and orientation are preserved, with decoding capped at the requested width. |
| Generic reflow options | The Librera document adapter opts into MuPDF's public per-context reflow settings. Application-specific choices stay in Librera; the library remains generic. |
| MuPDF-free flavours | `fdroidJS` / `proJS` retain their existing engines and Android WebP decoding. They exclude `libMuPDF.so`, do not load the image JNI decoder, and do not advertise JXL. |

At the codec integration update, MuPDF revision `71047a69f` bundles WebP 1.6.0
and libjxl 0.12.0, with Brotli, Highway, and skcms decoder dependencies. MuPDF
owns those pins and its SDK helper. Librera initializes the pinned sources and
refreshes the SDK each build; it does not clone an independent libjxl tree.
`Builder/build/mupdf-fork/build.json` records the actual MuPDF and codec commits.
Packaged codec notices live in `app/src/main/assets/native-codecs/` and are
refreshed from the build inputs.

Codec limits follow the MuPDF fork: JPEG XL output is 8-bit and animated JXL
uses the first coalesced frame; the native WebP decoder does not support
animation. These are input extensions, not WebP/JXL encoding support.

## Build and validate

Use the Gradle wrapper and the SDK/JDK configuration in this repository.
Configure signing/service properties as described in [README.md](README.md).
F-Droid flavours need no Firebase configuration. Native builds additionally
need Python 3, Make, CMake, Ninja, and the Android NDK (validated with r27d).

```sh
# Existing checkouts are used as-is; the script does not pull or switch branches.
# If absent, it clones vm75/mupdf's main branch to ../mupdf.
export LIBRERA_NDK_DIR=/path/to/android-ndk-r27d
Builder/link_to_mupdf_fork.sh
Builder/build-nomupdf.sh fork
./gradlew :app:assembleFdroidDebug :app:assembleFdroidJSDebug
```

Gradle automatically runs the MuPDF native build before native APK packaging.
The explicit first command also supplies the shared LAME library for JS-only
builds; `build-nomupdf.sh` supplies their auxiliary `libLibreraDocs.so`.
The default release and beta scripts select the fork; their explicit legacy
version arguments remain available. Use direct debug tasks for validation.

| Environment variable | `~/.gradle/gradle.properties` | Default |
| --- | --- | --- |
| `LIBRERA_MUPDF_DIR` | `librera_mupdf_dir` | sibling `../mupdf` |
| `LIBRERA_NDK_DIR` (or `ANDROID_NDK_HOME`) | `librera_ndk_dir` | required |
| `LIBRERA_FDROID_NDK_DIR` | `librera_fdroid_ndk_dir` | main NDK setting |
| `LIBRERA_JXL_SDK_DIR` | `librera_jxl_sdk_dir` | `Builder/build/mupdf-fork/jxl` |
| `LIBRERA_NATIVE_JOBS` | — | `4` |
| `LIBRERA_ABIS` | — | `armeabi-v7a arm64-v8a x86 x86_64` |

Environment settings take precedence; `GRADLE_USER_HOME` can relocate the user
properties file. Update the MuPDF checkout separately when intentionally
changing its source revision. A Librera upstream rebase does not update that checkout.

Lightweight checks, requiring Git, Python 3.9+, and Bash:

```sh
python3 scripts/test-rebase-fork.py
python3 Builder/tests/test_fork_build.py
```

For pixel-level checks of the production Java/JNI image bridge on Linux,
install a JDK and C/C++ build toolchain, initialize MuPDF's dependencies using
the native build above, then run:

```sh
make -C ../mupdf -j4 build=debug XCFLAGS=-fPIC OUT="$PWD/Builder/build/image-test-mupdf" libs
python3 Builder/tests/test_native_images.py --libraries Builder/build/image-test-mupdf
./gradlew :app:testFdroidDebugUnitTest
```

Pass `--mupdf /path/to/mupdf` to the image test if using a different checkout.
Use a fresh host output directory after changing compilers or build flags.
The JNI test covers WebP/JXL pixel output, transparency, orientation, resizing,
malformed input, and the MuPDF-free flavour guard. Device execution is still
needed to verify Android UI and end-to-end reader behaviour. At the integration
baseline, five existing tests fail in `TestPage` (whitespace expectation) and
`TestSync` (Android storage setup); distinguish these from new regressions.

## Keep fork commits above upstream

Use these remotes and tracking settings in each clone:

```sh
git remote -v
# Add upstream if it is absent:
git remote add upstream https://github.com/foobnix/LibreraReader.git
git config branch.main.remote origin
git config branch.main.merge refs/heads/main
git config branch.main.pushRemote origin
git config branch.main.rebase true
git config remote.pushDefault origin
git config rerere.enabled true
git config rerere.autoupdate false
```

`origin` must point to `git@github.com:vm75/LibreraReader.git` (HTTPS is also
usable). `main` tracks `origin/main`, while upstream updates are explicitly
rebased onto it. `rerere` remembers conflict resolutions; inspect reused
resolutions before staging them. Avoid merging upstream or using an ordinary
pull as a substitute for the fork update procedure.

Run [scripts/rebase-fork.py](scripts/rebase-fork.py) from this repository's
**clean `main` with all fork changes committed**. It refuses untracked/staged
work, other branches, pending Git operations, and merge commits in the fork
stack. It neither stashes changes nor commits existing work for you.

```sh
# Fetch upstream branches and tags, select the latest stable tag, and rebase.
python3 scripts/rebase-fork.py

# Or choose a specific upstream release / the development branch.
python3 scripts/rebase-fork.py --base 10.0.7
python3 scripts/rebase-fork.py --base upstream/master

# Preview already-fetched refs without changing anything.
python3 scripts/rebase-fork.py --dry-run
```

The default `latest-stable` means the highest upstream `X.Y.Z` or `vX.Y.Z` tag
by numeric version. Prerelease suffixes are excluded; this does not consult
GitHub's release designation. Upstream tags are fetched into the private
namespace `refs/fork/upstream-tags/*`, so fork release tags cannot influence
selection or be overwritten. A dry run needs those cached refs; it does not
fetch them. To refresh the cache before previewing without starting a rebase:

```sh
git fetch --prune --no-tags upstream '+refs/heads/*:refs/remotes/upstream/*' '+refs/tags/*:refs/fork/upstream-tags/*'
python3 scripts/rebase-fork.py --dry-run
```

Select a tag explicitly when reproducibility matters.

Each real run fetches upstream, resolves immutable old/new base commits, and
creates a `backup/main-<UTC timestamp>` branch. It saves the plan in Git's
`fork-rebase.json`, runs `git rebase --onto`, checks build-script orchestration
and shell syntax, prints a `git range-diff`, and records the new base in the
local ref `refs/fork/upstream-base`. Backups are protected from Git's
`rebase.updateRefs` setting. No push happens automatically.

The fork was established on upstream `10.0.7` (`31147f3ee`); the current base
is recorded in `refs/fork/upstream-base`. That local ref and Git configuration
are not cloned. On a fresh clone the helper
infers the previous base from `upstream/master`, rejecting ambiguous stacks.
When it asks for an explicit base, use the release the fork previously followed:

```sh
python3 scripts/rebase-fork.py --from-base 10.0.7 --base latest-stable
```

Do not substitute the desired new release for `--from-base`: that option marks
where the existing fork patch stack starts. Fork tags or release-branch-only
commits can require this explicit initial base.

### Conflicts and recovery

When Git stops, inspect `git status` and resolve each conflict by adapting the
fork extension to the new upstream implementation. Preserve both upstream fixes
and the fork's intent; do not blanket-accept either side. Pay particular
attention to Gradle task ordering/flavours, manifest registrations, JNI API
changes, format routing, extractor/Glide paths, and native source/dependency lists.

```sh
git status
git add <resolved-files>
python3 scripts/rebase-fork.py --continue
```

Repeat until done. The helper verifies that an active rebase matches its saved
plan. If checks fail after Git finishes, fix the issue, commit the repair, and
run `--continue` to retry checks without replaying the stack again.
`--skip-tests` explicitly defers its lightweight checks; it does not validate
APK packaging or native image decoding.

```sh
# During an active helper rebase, restore the original main:
python3 scripts/rebase-fork.py --abort
```

If Git has already finished rebasing, `--abort` refuses to reset history. Use
`--continue` to retry checks, or inspect the saved backup on a recovery branch.
The helper can cancel a pending plan if Git refused to start and `main` never
moved. Keep the backup until the new stack has been reviewed and validated.

### Review and publication

Review the range-diff, run the APK and host JNI checks above, and investigate
new test failures before publishing. A rebase changes fork commit IDs.
Fetch and review remote fork changes first; then, when publishing is intended:

```sh
git fetch origin
git log --oneline main..origin/main
# After reconciling any remote work and reviewing the expected remote tip:
git push --force-with-lease origin main:main
```

Remote changes must be included or deliberately reconciled before pushing;
fetching alone does not make an overwrite appropriate. Initial publication can
use `git push --set-upstream origin main`. The script updates only local history.
Existing [Librera licensing](LICENSE.txt) and the bundled component notices apply.
