LOCAL_PATH:= $(call my-dir)
include $(CLEAR_VARS)

LOCAL_MODULE:= libttscompat
LOCAL_MODULE_TAGS := optional

LOCAL_SRC_FILES:= \
	android_tts_SynthProxy.cpp

LOCAL_C_INCLUDES += \
	frameworks/base/native/include \
	$(JNI_H_INCLUDE)

LOCAL_SHARED_LIBRARIES := \
	libandroid_runtime \
	libnativehelper \
	libmedia \
	libutils \
	libcutils

LOCAL_SHARED_LIBRARIES += libdl

LOCAL_ARM_MODE := arm

include $(BUILD_SHARED_LIBRARY)
