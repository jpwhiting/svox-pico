#
# Installation of it-IT for the Pico TTS engine in the system image
# 
# Include this file in a product makefile to include the language files for it-IT
#
# Note the destination path matches that used in external/svox/pico/tts/com_svox_picottsengine.cpp
# 

LOCAL_PATH:= external/svox/pico/lang

PRODUCT_COPY_FILES += \
	$(LOCAL_PATH)/it-IT_cm0_sg.bin:system/tts/lang_pico/it-IT_cm0_sg.bin \
	$(LOCAL_PATH)/it-IT_ta.bin:system/tts/lang_pico/it-IT_ta.bin

