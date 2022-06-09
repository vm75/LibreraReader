#!/bin/bash

SCRIPT=$(realpath "${0}")
SCRIPT_DIR=$(dirname "${SCRIPT}")
PROJECT_ROOT=$(dirname "${SCRIPT_DIR}")
JNI_DIR=${PROJECT_ROOT}/jni
APP_DIR=${PROJECT_ROOT}/app

init() {
    cd "${PROJECT_ROOT}"
    git submodule update --init --recursive .

    cd "${JNI_DIR}/3rdparty"
    for patch in *.patch ; do
        module=${patch%.patch}
        cd ${module}
        git reset --hard HEAD
        git clean -f -d
        git apply ../${patch}
        cd -
    done
}

refreshPatches() {
    cd "${JNI_DIR}/3rdparty"

    for patch in *.patch ; do
        module=${patch%.patch}
        cd ${module}
        git add * .git*
        git diff --staged > ../${patch}
        cd -
    done
}

buildJni() {
    rm -f "${APP_DIR}/src/main/jniLibs/*"
    cd "${JNI_DIR}"
    ndk-build NDK_LIBS_OUT="${APP_DIR}/src/main/jniLibs" NDK_OUT="${JNI_DIR}/obj"
}

buildApp() {
    cd "${PROJECT_ROOT}"
    ./gradlew assembleProRelease
}

main() {
    command=$1 ; shift

    case "${command}" in
    i|init)
        init
        ;;
    s|save-patch)
        refreshPatches
        ;;
    j|build-jni)
        buildJni
        ;;
    a|build-app)
        buildApp
        ;;
    b|build)
        buildJni
        buildApp
        ;;
    esac
}

main "$@"
