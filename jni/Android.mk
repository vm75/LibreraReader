TOP_LOCAL_PATH:= $(call my-dir)
include $(CLEAR_VARS)

ANTIWORD_ROOT := $(TOP_LOCAL_PATH)/3rdparty/antiword
DJVU_ROOT := $(TOP_LOCAL_PATH)/3rdparty/djvu
HQX_ROOT := $(TOP_LOCAL_PATH)/3rdparty/hqx
LIBMOBI_ROOT := $(TOP_LOCAL_PATH)/3rdparty/libmobi
LIBWEBP_ROOT := $(TOP_LOCAL_PATH)/3rdparty/libwebp
MUPDF_ROOT := $(TOP_LOCAL_PATH)/3rdparty/mupdf

include $(TOP_LOCAL_PATH)/3rdparty/antiword/Android.mk
include $(TOP_LOCAL_PATH)/3rdparty/djvu/Android.mk
include $(TOP_LOCAL_PATH)/3rdparty/hqx/Android.mk
include $(TOP_LOCAL_PATH)/3rdparty/libmobi/Android.mk
include $(TOP_LOCAL_PATH)/3rdparty/mupdf/Android.mk
include $(CLEAR_VARS)

LOCAL_ARM_MODE := $(MY_ARM_MODE)

LOCAL_ARM_NEON := true

LOCAL_C_INCLUDES := \
	$(DJVU_ROOT)/libdjvu \
	$(HQX_ROOT)/src \
	$(LIBMOBI_ROOT)/src \
	$(LIBMOBI_ROOT)/tools \
	$(MUPDF_ROOT)/include \
	$(MUPDF_ROOT)/source/fitz \
	$(MUPDF_ROOT)/source/pdf \
	$(TOP_LOCAL_PATH)/src

LOCAL_CFLAGS := -DHAVE_ANDROID
LOCAL_MODULE := Librera

LOCAL_SRC_FILES := \
	$(TOP_LOCAL_PATH)/src/ebookdroidjni.c \
	$(TOP_LOCAL_PATH)/src/djvuDroidBridge.cpp \
	$(TOP_LOCAL_PATH)/src/cbdroidbridge.c \
	$(TOP_LOCAL_PATH)/src/jni_concurrent.c \
	$(TOP_LOCAL_PATH)/src/libmupdf.c

LOCAL_STATIC_LIBRARIES := djvu hqx mupdf_java
LOCAL_LDLIBS := -lm -llog -ljnigraphics

include $(BUILD_SHARED_LIBRARY)
