# SVOX Pico TTS Engine
# This makefile builds both an activity and a shared library.

ifneq ($(TARGET_SIMULATOR),true) # not 64 bit clean

TOP_LOCAL_PATH:= $(call my-dir)

# Build Pico activity

LOCAL_PATH:= $(call my-dir)
include $(CLEAR_VARS)

LOCAL_MODULE_TAGS := optional

LOCAL_SRC_FILES := $(call all-subdir-java-files)

LOCAL_PACKAGE_NAME := PicoTts

include $(BUILD_PACKAGE)

# Build Pico Shared Library

LOCAL_PATH:= $(TOP_LOCAL_PATH)/tts
include $(CLEAR_VARS)

LOCAL_SRC_FILES:= com_svox_picottsengine.cpp svox_ssml_parser.cpp

LOCAL_C_INCLUDES += \
	external/svox/pico/lib \
	frameworks

LOCAL_STATIC_LIBRARIES:= libsvoxpico

LOCAL_SHARED_LIBRARIES:= libcutils libexpat libutils

LOCAL_MODULE:= libttspico

LOCAL_ARM_MODE:= arm

include $(BUILD_SHARED_LIBRARY)


# Build Base Generic SVOX Pico Library
LOCAL_PATH:= $(TOP_LOCAL_PATH)/lib
include $(CLEAR_VARS)

LOCAL_SRC_FILES:= \
	picoacph.c \
	picoapi.c \
	picobase.c \
	picocep.c \
	picoctrl.c \
	picodata.c \
	picodbg.c \
	picoextapi.c \
	picofftsg.c \
	picokdbg.c \
	picokdt.c \
	picokfst.c \
	picoklex.c \
	picoknow.c \
	picokpdf.c \
	picokpr.c \
	picoktab.c \
	picoos.c \
	picopal.c \
	picopam.c \
	picopr.c \
	picorsrc.c \
	picosa.c \
	picosig.c \
	picosig2.c \
	picospho.c \
	picotok.c \
	picotrns.c \
	picowa.c

LOCAL_PRELINK_MODULE:= false

LOCAL_MODULE:= libsvoxpico

LOCAL_CFLAGS+= $(TOOL_CFLAGS)

LOCAL_LDFLAGS+= $(TOOL_LDFLAGS)

include $(BUILD_STATIC_LIBRARY)

endif # TARGET_SIMULATOR
