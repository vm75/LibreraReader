#!/bin/bash

SCRIPT=$(realpath "${0}")
SCRIPT_DIR=$(dirname "${SCRIPT}")
PROJECT_ROOT=$(dirname "${SCRIPT_DIR}")
JNI_DIR=${PROJECT_ROOT}/jni
APP_DIR=${PROJECT_ROOT}/app

applyPatch() {
    module=$1
    cd ${module}
    git reset --hard HEAD
    git clean -f -d
    git apply ../${module}.patch
    cd -
}

main() {
    cd "${PROJECT_ROOT}"

    cd "${JNI_DIR}/3rdparty"
    for module in djvu hqx libmobi libwebp ; do
        git submodule update --init --recursive ${module}
        applyPatch ${module}
    done

    if [[ $1 == beta ]] ; then
        mupdf=mupdf-1.20
        beta="BETA=1"
    else
        mupdf=mupdf-1.11
    fi

    applyPatch ${mupdf}
    git submodule update --init --recursive ${mupdf}
    if [[ ! -d ${mupdf}/generate ]] ; then
        cd ${mupdf}
        make generate
        cd -
    fi

    rm -f "${APP_DIR}/src/main/jniLibs/*"
    cd "${JNI_DIR}"

    ndk-build ${beta} NDK_LIBS_OUT="${APP_DIR}/src/main/jniLibs" NDK_OUT="${JNI_DIR}/obj"
}

main "$@"
