LOCAL_PATH := $(call my-dir)
LIBRERA_JNI_PATH := $(LOCAL_PATH)
LIBRERA_MUPDF_ROOT ?= $(abspath $(LIBRERA_JNI_PATH)/../../../mupdf)

# Reuse the fork's codec/dependency modules instead of copying its source files.
MUPDF_JNI_STATIC := yes
include $(LIBRERA_MUPDF_ROOT)/platform/java/Android.mk

MUPDF_ROOT := $(LIBRERA_MUPDF_ROOT)
include $(LIBRERA_JNI_PATH)/libmobi-0.12/Android.mk
include $(LIBRERA_JNI_PATH)/libhqx-1.2/Android.mk
include $(LIBRERA_JNI_PATH)/libdjvu-3.5.28/Android.mk
include $(LIBRERA_JNI_PATH)/libantiword-1.3.1/Android.mk
include $(LIBRERA_JNI_PATH)/liblame-1.0.9/Android.mk

include $(CLEAR_VARS)
LOCAL_PATH := $(LIBRERA_JNI_PATH)
LOCAL_MODULE := MuPDF
LOCAL_ARM_MODE := $(APP_ARM_MODE)
LOCAL_CFLAGS := -DHAVE_ANDROID
LOCAL_C_INCLUDES := $(LIBRERA_MUPDF_ROOT)/include \
    $(LIBRERA_MUPDF_ROOT)/source/fitz \
    $(LIBRERA_MUPDF_ROOT)/source/pdf \
    $(LIBRERA_JNI_PATH) \
    $(LIBRERA_JNI_PATH)/libdjvu-3.5.28/src \
    $(LIBRERA_JNI_PATH)/libhqx-1.2
LOCAL_SRC_FILES := ebookdroidjni.c DjvuDroidBridge.cpp cbdroidbridge.c \
    jni_concurrent.c androidfonts.c libmupdf_librera_fork.c mupdf-image.c
LOCAL_STATIC_LIBRARIES := djvu hqx mupdf_java
LOCAL_WHOLE_STATIC_LIBRARIES := antiword libmobi_012
LOCAL_LDLIBS := -ljnigraphics -llog -lz -lm
LOCAL_LDLIBS += $(MUPDF_EXTRA_LDLIBS)
LOCAL_LDFLAGS += $(MUPDF_EXTRA_LDFLAGS)
include $(BUILD_SHARED_LIBRARY)
