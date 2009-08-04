#
# Installation of es-ES for the Pico TTS engine in the system image
# 
# Include this file in a product makefile to include the language files for es-ES
#
# Note the destination path matches that used in external/svox/pico/tts/com_svox_picottsengine.cpp
# 

LOCAL_PATH:= external/svox/pico/lang

PRODUCT_COPY_FILES += \
	$(LOCAL_PATH)/es-ES_zl0_sg.bin:system/tts/lang_pico/es-ES_zl0_sg.bin \
	$(LOCAL_PATH)/es-ES_ta.bin:system/tts/lang_pico/es-ES_ta.bin

