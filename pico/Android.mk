# SVOX Pico TTS Engine
# This makefile builds both an activity and a shared library.

TOP_LOCAL_PATH:= $(call my-dir)

# Build Pico activity

LOCAL_PATH:= $(call my-dir)
include $(CLEAR_VARS)

LOCAL_MODULE_TAGS := optional

LOCAL_SRC_FILES := $(call all-java-files-under, src) \
    $(call all-java-files-under, compat)

LOCAL_PACKAGE_NAME := PicoTts
LOCAL_REQUIRED_MODULES := libttscompat libttspico

LOCAL_PROGUARD_FLAG_FILES := proguard.flags

include $(BUILD_PACKAGE)

# Build static library containing all PICO code
# excluding the compatibility code. This is identical
# to the rule below / except that it builds a shared
# library.
LOCAL_PATH:= $(TOP_LOCAL_PATH)/tts
include $(CLEAR_VARS)

LOCAL_MODULE_TAGS := optional

LOCAL_SRC_FILES:= com_svox_picottsengine.cpp svox_ssml_parser.cpp

LOCAL_C_INCLUDES += \
	external/svox/pico/lib \
	external/svox/pico/compat/include

LOCAL_STATIC_LIBRARIES:= libsvoxpico

LOCAL_SHARED_LIBRARIES:= libcutils libexpat libutils

LOCAL_MODULE:= libttspico_engine

LOCAL_ARM_MODE:= arm

include $(BUILD_STATIC_LIBRARY)

# Build Pico Shared Library. This rule is used by the
# compatibility code, which opens this shared library
# using dlsym. This is essentially the same as the rule
# above, except that it packages things a shared library.
LOCAL_PATH:= $(TOP_LOCAL_PATH)/tts
include $(CLEAR_VARS)

LOCAL_MODULE_TAGS := optional

LOCAL_SRC_FILES:= com_svox_picottsengine.cpp svox_ssml_parser.cpp
LOCAL_C_INCLUDES += \
	external/svox/pico/lib \
	external/svox/pico/compat/include
LOCAL_STATIC_LIBRARIES:= libsvoxpico
LOCAL_SHARED_LIBRARIES:= libcutils libexpat libutils
LOCAL_MODULE:= libttspico

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



LOCAL_MODULE:= libsvoxpico

LOCAL_CFLAGS+= $(TOOL_CFLAGS)

LOCAL_LDFLAGS+= $(TOOL_LDFLAGS)

include $(BUILD_STATIC_LIBRARY)


# Build compatibility library
LOCAL_PATH:= $(TOP_LOCAL_PATH)/compat/jni
include $(CLEAR_VARS)

LOCAL_MODULE:= libttscompat
LOCAL_MODULE_TAGS := optional

LOCAL_SRC_FILES:= \
        com_android_tts_compat_SynthProxy.cpp

LOCAL_SHARED_LIBRARIES := \
        libandroid_runtime \
        libnativehelper \
        libmedia \
        libutils \
        libcutils \
        libdl

include $(BUILD_SHARED_LIBRARY)
