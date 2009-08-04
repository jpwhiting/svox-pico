#
# Installation of en-US for the Pico TTS engine in the system image
# 
# Include this file in a product makefile to include the language files for english US
#
# Note the destination path matches that used in external/svox/pico/tts/com_svox_picottsengine.cpp
# 

LOCAL_PATH:= external/svox/pico/lang

PRODUCT_COPY_FILES += \
	$(LOCAL_PATH)/en-US_lh0_sg.bin:system/tts/lang_pico/en-US_lh0_sg.bin \
	$(LOCAL_PATH)/en-US_ta.bin:system/tts/lang_pico/en-US_ta.bin

