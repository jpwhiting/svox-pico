/*
 * Copyright (C) 2008-2009 SVOX AG, Baslerstr. 30, 8048 Zuerich, Switzerland
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * History:
 * 2009-05-18 -- initial version
 * 2009-06-04 -- updated for new TtsEngine interface
 *
 */

#include <stdio.h>
#include <unistd.h>

#define LOG_TAG "SVOX Pico Engine"

#include <utils/Log.h>
#include <android_runtime/AndroidRuntime.h>
#include <tts/TtsEngine.h>
#include <picoapi.h>
#include <picodefs.h>

using namespace android;

/* adaptation layer defines */
#define PICO_MEM_SIZE       2500000 
#define PICO_MIN_RATE       20
#define PICO_DEF_RATE       100
#define PICO_MAX_RATE       500
#define PICO_MIN_PITCH      50
#define PICO_DEF_PITCH      100
#define PICO_MAX_PITCH      200
#define PICO_MIN_VOLUME     0
#define PICO_DEF_VOLUME     100
#define PICO_MAX_VOLUME     500
#define MAX_OUTBUF_SIZE     128
const char* PICO_LINGWARE_PATH              = "/sdcard/svox/";
const char* PICO_VOICE_NAME                 = "PicoVoice";
const char* PICO_SPEED_OPEN_TAG             = "<speed level='%d'>";
const char* PICO_SPEED_CLOSE_TAG            = "</speed>";
const char* PICO_PITCH_OPEN_TAG             = "<pitch level='%d'>";
const char* PICO_PITCH_CLOSE_TAG            = "</pitch>";
const char* PICO_VOLUME_OPEN_TAG            = "<volume level='%d'>";
const char* PICO_VOLUME_CLOSE_TAG           = "</volume>";

const char* picoSupportedLang[]             = { "en-rUS",           "en-rGB",           "de-rDE",           "es-rES",           "fr-rFR",           "it-rIT" };
const char* picoInternalLang[]              = { "en-US",            "en-GB",            "de-DE",            "es-ES",            "fr-FR",            "it-IT" };
const char* picoInternalTaLingware[]        = { "en-US_ta.bin",     "en-GB_ta.bin",     "de-DE_ta.bin",     "es-ES_ta.bin",     "fr-FR_ta.bin",     "it-IT_ta.bin" };
const char* picoInternalSgLingware[]        = { "en-US_lh0_sg.bin", "en-GB_kh0_sg.bin", "de-DE_gl0_sg.bin", "es-ES_zl0_sg.bin", "fr-FR_nk0_sg.bin", "it-IT_cm0_sg.bin" };
const char* picoInternalUtppLingware[]      = { "en-US_utpp.bin",   "en-GB_utpp.bin",   "de-DE_utpp.bin",   "es-ES_utpp.bin",   "fr-FR_utpp.bin",   "it-IT_utpp.bin" };
const int picoNumSupportedLang              = 6;

const char* picoSupportedProperties[]       = { "language", "rate", "pitch", "volume" };
const int picoNumSupportedProperties        = 4;

/* adapation layer globals */
synthDoneCB_t* picoSynthDoneCBPtr;
void* picoMemArea = NULL;
pico_System picoSystem = NULL;
pico_Resource picoTaResource = NULL;
pico_Resource picoSgResource = NULL;
pico_Resource picoUtppResource = NULL;
pico_Engine picoEngine = NULL;
pico_Char* picoTaFileName = NULL;
pico_Char* picoSgFileName = NULL;
pico_Char* picoUtppFileName = NULL;
pico_Char* picoTaResourceName = NULL;
pico_Char* picoSgResourceName = NULL;
pico_Char* picoUtppResourceName = NULL;
int picoSynthAbort = 0;
char* picoProp_currLang = NULL;
int picoProp_currRate = PICO_DEF_RATE;
int picoProp_currPitch = PICO_DEF_PITCH;
int picoProp_currVolume = PICO_DEF_VOLUME;


/* internal helper functions */

/** checkForLanguage
 *  Checks if the requested language is among the supported languages
 *  @language -  the language to check, either in xx or xx-rYY format
 *  return index of the language, or -1 if not supported
*/
static int checkForLanguage(const char* language)
{
    // verify that it's a language we support
    int found = -1;
    for (int i = 0; i < picoNumSupportedLang; i++)
    {
        if (strcmp(language, picoSupportedLang[i]) == 0)
        {
            found = i;
            break;
        }
    }
    if (found < 0)
    {
        // didn't find an exact match, may have been specified with only the first 2 characters
        for (int i = 0; i < picoNumSupportedLang; i++)
        {
            if (strncmp(language, picoSupportedLang[i], 2) == 0)
            {
                found = i;
                break;
            }
        }
        if (found < 0)
        {
            LOGE("TtsEngine::set language called with unsupported language");
        }
    }
    return found;
}

/** cleanResources
 *  Unloads any loaded pico resources
*/
static void cleanResources()
{
    if (picoEngine)
    {
        pico_disposeEngine(picoSystem, &picoEngine);
        pico_releaseVoiceDefinition(picoSystem, (pico_Char*)PICO_VOICE_NAME);
        picoEngine = NULL;
    }
    if (picoUtppResource)
    {
        pico_unloadResource(picoSystem, &picoUtppResource);
        picoUtppResource = NULL;
    }
    if (picoTaResource)
    {
        pico_unloadResource(picoSystem, &picoTaResource);
        picoTaResource = NULL;
    }
    if (picoSgResource)
    {
        pico_unloadResource(picoSystem, &picoSgResource);
        picoSgResource = NULL;
    }
}

/** cleanFiles
 *  Frees any memory allocated for file and resource strings
*/
static void cleanFiles()
{
    if (picoProp_currLang)
    {
        free(picoProp_currLang);
        picoProp_currLang = NULL;
    }
    
    if (picoTaFileName)
    {
        free(picoTaFileName);
        picoTaFileName = NULL;
    }
    
    if (picoSgFileName)
    {
        free(picoSgFileName);
        picoSgFileName = NULL;
    }
    
    if (picoUtppFileName)
    {
        free(picoUtppFileName);
        picoUtppFileName = NULL;
    }
    
    if (picoTaResourceName)
    {
        free(picoTaResourceName);
        picoTaResourceName = NULL;
    }
    
    if (picoSgResourceName)
    {
        free(picoSgResourceName);
        picoSgResourceName = NULL;
    }
    
    if (picoUtppResourceName)
    {
        free(picoUtppResourceName);
        picoUtppResourceName = NULL;
    }
}

/** doLanguageSwitch
 *  Switch to requested language. If language is already loaded it returns
 *  immediately, if another language is loaded this will first be unloaded
 *  and the new one then loaded. If no language is loaded the requested will be loaded.
 *  @language -  the language to check, either in xx or xx-rYY format (i.e "en" or "en-rUS")
 *  return TTS_SUCCESS or TTS_FAILURE
*/
static int doLanguageSwitch(const char* language)
{
    // load new language
    int langIndex = checkForLanguage(language);
    if (langIndex < 0)
    {
        LOGE("Tried to swith to non-supported language %s", language);
        return TTS_FAILURE;
    }
    LOGI("Found supported language %s", picoSupportedLang[langIndex]);
    
    // if we already have a loaded language, check if it's the same one as requested
    if (picoProp_currLang && (strcmp(picoProp_currLang, picoSupportedLang[langIndex]) == 0))
    {
        LOGI("Language %s already loaded (%s == %s)", language, picoProp_currLang, picoSupportedLang[langIndex]);
        return TTS_SUCCESS;
    }

    // not the same language, unload the current one first
    cleanResources();
    
    // allocate memory for file and resource names
    cleanFiles();
    picoProp_currLang = (char*)malloc(10);
    picoTaFileName = (pico_Char*)malloc(PICO_MAX_DATAPATH_NAME_SIZE + PICO_MAX_FILE_NAME_SIZE);
    picoSgFileName = (pico_Char*)malloc(PICO_MAX_DATAPATH_NAME_SIZE + PICO_MAX_FILE_NAME_SIZE);
    picoUtppFileName = (pico_Char*)malloc(PICO_MAX_DATAPATH_NAME_SIZE + PICO_MAX_FILE_NAME_SIZE);
    picoTaResourceName = (pico_Char*)malloc(PICO_MAX_RESOURCE_NAME_SIZE);
    picoSgResourceName = (pico_Char*)malloc(PICO_MAX_RESOURCE_NAME_SIZE);
    picoUtppResourceName = (pico_Char*)malloc(PICO_MAX_RESOURCE_NAME_SIZE);
    
    // set path and file names for resource files
    strcpy((char*)picoTaFileName, PICO_LINGWARE_PATH);
    strcat((char*)picoTaFileName, (const char*)picoInternalTaLingware[langIndex]);
    strcpy((char*)picoSgFileName, PICO_LINGWARE_PATH);
    strcat((char*)picoSgFileName, (const char*)picoInternalSgLingware[langIndex]);
    strcpy((char*)picoUtppFileName, PICO_LINGWARE_PATH);
    strcat((char*)picoUtppFileName, (const char*)picoInternalUtppLingware[langIndex]);
    
    // load text analysis Lingware resource file
    int ret = pico_loadResource(picoSystem, picoTaFileName, &picoTaResource);
    if (PICO_OK != ret)
    {
        LOGE("Failed to load textana resource for %s [%d]", language, ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }
    
    // load signal generation Lingware resource file
    ret = pico_loadResource(picoSystem, picoSgFileName, &picoSgResource);
    if (PICO_OK != ret)
    {
        LOGE("Failed to load siggen resource for %s [%d]", language, ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }
    
    // Load utpp Lingware resource file if exists - NOTE: this file is optional
    // and is currently not used. Loading is only attempted for future compatibility.
    // If this file is not present the loading will still succeed.
    ret = pico_loadResource(picoSystem, picoUtppFileName, &picoUtppResource);
    if (PICO_OK != ret && ret != PICO_EXC_CANT_OPEN_FILE)
    {
        LOGE("Failed to load utpp resource for %s [%d]", language, ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }
    
    // Get text analysis resource name
    ret = pico_getResourceName(picoSystem, picoTaResource, (char*)picoTaResourceName);
    if (PICO_OK != ret)
    {
        LOGE("Failed to get textana resource name for %s [%d]", language, ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }
    
    // Get signal generation resource name
    ret = pico_getResourceName(picoSystem, picoSgResource, (char*)picoSgResourceName);
    if (PICO_OK == ret && picoUtppResource != NULL)
    {
        // Get utpp resource name - optional: see note above
        ret = pico_getResourceName(picoSystem, picoUtppResource, (char*)picoUtppResourceName);
        if (PICO_OK != ret)
        {
            LOGE("Failed to get utpp resource name for %s [%d]", language, ret);
            cleanResources();
            cleanFiles();
            return TTS_FAILURE;
        }
    }
    if (PICO_OK != ret)
    {
        LOGE("Failed to get siggen resource name for %s [%d]", language, ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }
    
    // create a voice definition
    ret = pico_createVoiceDefinition(picoSystem, (const pico_Char*)PICO_VOICE_NAME);
    if (PICO_OK != ret)
    {
        LOGE("Failed to create voice for %s [%d]", language, ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }
    
    // add text analysis resource to voice
    ret = pico_addResourceToVoiceDefinition(picoSystem, (const pico_Char*)PICO_VOICE_NAME, picoTaResourceName);
    if (PICO_OK != ret)
    {
        LOGE("Failed to add textana resource to voice for %s [%d]", language, ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }
    
    // add signal generation resource to voice
    ret = pico_addResourceToVoiceDefinition(picoSystem, (const pico_Char*)PICO_VOICE_NAME, picoSgResourceName);
    if (PICO_OK == ret && picoUtppResource != NULL)
    {
        // add utpp resource to voice - optional: see note above
        ret = pico_addResourceToVoiceDefinition(picoSystem, (const pico_Char*)PICO_VOICE_NAME, picoUtppResourceName);
        if (PICO_OK != ret)
        {
            LOGE("Failed to add utpp resource to voice for %s [%d]", language, ret);
            cleanResources();
            cleanFiles();
            return TTS_FAILURE;
        }
    }
    
    if (PICO_OK != ret)
    {
        LOGE("Failed to add siggen resource to voice for %s [%d]", language, ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }

    ret = pico_newEngine(picoSystem, (const pico_Char*)PICO_VOICE_NAME, &picoEngine);
    if (PICO_OK != ret)
    {
        LOGE("Failed to create engine for %s [%d]", language, ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }
    
    strcpy(picoProp_currLang, picoSupportedLang[langIndex]);
    
    LOGI("loaded %s successfully", picoProp_currLang);
        
    return TTS_SUCCESS;
}

/** doAddProperties
 *  add <speed>, <pitch> and <volume> tags to text if properties have been set to non-default values
 *  and returns the new string. Calling function is responsible for freeing returned string
 *  @str - text to apply tags to
 *  return new string with tags applied
*/
static char* doAddProperties(const char* str)
{
    char* data = NULL;
    int haspitch = 0, hasspeed = 0, hasvol = 0;
    int textlen = strlen(str) + 1;
    
    if (picoProp_currPitch != PICO_DEF_PITCH)
    {
        textlen += strlen(PICO_PITCH_OPEN_TAG) + 5;
        textlen += strlen(PICO_PITCH_CLOSE_TAG);
        haspitch = 1;
    }
    if (picoProp_currRate != PICO_DEF_RATE)
    {
        textlen += strlen(PICO_SPEED_OPEN_TAG) + 5;
        textlen += strlen(PICO_SPEED_CLOSE_TAG);
        hasspeed = 1;
    }
    if (picoProp_currVolume != PICO_DEF_VOLUME)
    {
        textlen += strlen(PICO_VOLUME_OPEN_TAG) + 5;
        textlen += strlen(PICO_VOLUME_CLOSE_TAG);
        hasvol = 1;
    }
    
    data = (char*)malloc(textlen);
    if (!data)
    {
        return NULL;
    }
    memset(data, 0, textlen);   
    if (haspitch)
    {
        char* tmp = (char*)malloc(strlen(PICO_PITCH_OPEN_TAG) + strlen(PICO_PITCH_CLOSE_TAG) + 5);
        sprintf(tmp, PICO_PITCH_OPEN_TAG, picoProp_currPitch);
        strcat(data, tmp);
        free(tmp);
    }
    
    if (hasspeed)
    {
        char* tmp = (char*)malloc(strlen(PICO_SPEED_OPEN_TAG) + strlen(PICO_SPEED_CLOSE_TAG) + 5);
        sprintf(tmp, PICO_SPEED_OPEN_TAG, picoProp_currRate);
        strcat(data, tmp);
        free(tmp);
    }
    
    if (hasvol)
    {
        char* tmp = (char*)malloc(strlen(PICO_VOLUME_OPEN_TAG) + strlen(PICO_VOLUME_CLOSE_TAG) + 5);
        sprintf(tmp, PICO_VOLUME_OPEN_TAG, picoProp_currVolume);
        strcat(data, tmp);
        free(tmp);
    }
    
    strcat(data, str);
    
    if (hasvol)
    {
        strcat(data, PICO_VOLUME_CLOSE_TAG);
    }
    
    if (hasspeed)
    {
        strcat(data, PICO_SPEED_CLOSE_TAG);
    }
    
    if (haspitch)
    {
        strcat(data, PICO_PITCH_CLOSE_TAG);
    }
    
    return data;
}

/* API function implementations */

/** init
 *  allocates pico memory block and initializes pico system
 *  synthDoneCBPtr - Pointer to callback function which will receive generated samples
 *  return tts_result
*/
tts_result TtsEngine::init(synthDoneCB_t synthDoneCBPtr)
{
    if (synthDoneCBPtr == NULL)
    {
        LOGE("Callback pointer is NULL");
        return TTS_FAILURE;
    }
    
    picoMemArea = malloc(PICO_MEM_SIZE);
    if (!picoMemArea)
    {
        LOGE("Failed to allocate memory for Pico system");
        return TTS_FAILURE;
    }
    
    pico_Status ret = pico_initialize(picoMemArea, PICO_MEM_SIZE, &picoSystem);
    if (PICO_OK != ret)
    {
        LOGE("Failed to initialize Pico system");
        free(picoMemArea);
        picoMemArea = NULL;
        return TTS_FAILURE;
    }
    
    picoSynthDoneCBPtr = synthDoneCBPtr;
    return TTS_SUCCESS;
}

/** shutdown
 *  unloads all pico resources, terminates pico system and frees pico memory block
 *  return tts_result
*/
tts_result TtsEngine::shutdown()
{
    cleanResources();
    
    if (picoSystem)
    {
        pico_terminate(&picoSystem);
        picoSystem = NULL;
    }
    if (picoMemArea)
    {
        free(picoMemArea);
        picoMemArea = NULL;
    }
    
    cleanFiles();
    
    return TTS_SUCCESS;
}

/** loadLanguage
 *  Load a new language
 *  @value - language string in xx or xx-rYY format (i.e. "en" or "en-rUS")
 *  @size - size of value
 *  return tts_result
*/
tts_result TtsEngine::loadLanguage(const char *value, const size_t size)
{
    return setProperty("language", value, size);
}

/** setLanguage
 *  Load a new language
 *  @value - language string in xx or xx-rYY format (i.e. "en" or "en-rUS")
 *  @size - size of value
 *  return tts_result
*/
tts_result TtsEngine::setLanguage(const char *value, const size_t size)
{
    return setProperty("language", value, size);
}

/** getLanguage
 *  Get currently loaded language - if any
 *  @value - buffer which will receive value
 *  @iosize - size of value - if value is too small to contain the return string, this will contain the actual size needed
 *  return tts_result
*/
tts_result TtsEngine::getLanguage(char *value, size_t *iosize)
{
    return getProperty("language", value, iosize);
}

/** setProperty
 *  set property, supported properties are language, rate, pitch and volume
 *  @property - name of property to set
 *  @value - value to set
 *  @size - size of value
 *  return tts_result
*/
tts_result TtsEngine::setProperty(const char *property, const char *value, const size_t size)
{
    // sanity check
    if (property == NULL)
    {
        LOGE("setProperty called with property NULL");
        return TTS_PROPERTY_UNSUPPORTED;
    }
    
    if (value == NULL)
    {
        LOGE("setProperty called with value NULL");
        return TTS_VALUE_INVALID;
    }
    
    if (strncmp(property, "language", 8) == 0)
    {
        // verify it's in correct format
        if (strlen(value) != 2 && strlen(value) != 6)
        {
            LOGE("change language called with incorrect format");
            return TTS_VALUE_INVALID;
        }
        
        // try to switch to specified language
        if (doLanguageSwitch(value) == TTS_FAILURE)
        {
            LOGE("failed to load language");
            return TTS_FAILURE;
        }
        else
        {
            return TTS_SUCCESS;
        }
    }
    else if (strncmp(property, "rate", 4) == 0)
    {
        int rate = atoi(value);
        if (rate < PICO_MIN_RATE) rate = PICO_MIN_RATE;
        if (rate > PICO_MAX_RATE) rate = PICO_MAX_RATE;
        picoProp_currRate = rate;
        return TTS_SUCCESS;
    }
    else if (strncmp(property, "pitch", 5) == 0)
    {
        int pitch = atoi(value);
        if (pitch < PICO_MIN_PITCH) pitch = PICO_MIN_PITCH;
        if (pitch > PICO_MAX_PITCH) pitch = PICO_MAX_PITCH;
        picoProp_currPitch = pitch;
        return TTS_SUCCESS;
    }
    else if (strncmp(property, "volume", 6) == 0)
    {
        int volume = atoi(value);
        if (volume < PICO_MIN_VOLUME) volume = PICO_MIN_VOLUME;
        if (volume > PICO_MAX_VOLUME) volume = PICO_MAX_VOLUME;
        picoProp_currVolume = volume;
        return TTS_SUCCESS;
    }

    return TTS_PROPERTY_UNSUPPORTED;
}

/** getProperty
 *  get property, supported properties are language, rate, pitch and volume
 *  @property - name of property to get
 *  @value - buffer which will receive value of property
 *  @iosize - size of value - if size is too small on return this will contain actual size needed
 *  return tts_result
*/
tts_result TtsEngine::getProperty(const char *property, char *value, size_t* iosize)
{
    // sanity check
    if (property == NULL)
    {
        LOGE("getProperty called with property NULL");
        return TTS_PROPERTY_UNSUPPORTED;
    }
    
    if (value == NULL)
    {
        LOGE("getProperty called with value NULL");
        return TTS_VALUE_INVALID;
    }
    
    if (strncmp(property, "language", 8) == 0)
    {
        if (picoProp_currLang == NULL)
        {
            strcpy(value, "");
        }
        else
        {
            if (*iosize < strlen(picoProp_currLang)+1)
            {
                *iosize = strlen(picoProp_currLang) + 1;
                return TTS_PROPERTY_SIZE_TOO_SMALL;
            }
            strcpy(value, picoProp_currLang);
        }
        return TTS_SUCCESS;
    }
    else if (strncmp(property, "rate", 4) == 0)
    {
        char tmprate[4];
        sprintf(tmprate, "%d", picoProp_currRate);
        if (*iosize < strlen(tmprate)+1)
        {
            *iosize = strlen(tmprate) + 1;
            return TTS_PROPERTY_SIZE_TOO_SMALL;
        }
        strcpy(value, tmprate);
        return TTS_SUCCESS;
    }
    else if (strncmp(property, "pitch", 5) == 0)
    {
        char tmppitch[4];
        sprintf(tmppitch, "%d", picoProp_currPitch);
        if (*iosize < strlen(tmppitch)+1)
        {
            *iosize = strlen(tmppitch) + 1;
            return TTS_PROPERTY_SIZE_TOO_SMALL;
        }
        strcpy(value, tmppitch);
        return TTS_SUCCESS;
    }
    else if (strncmp(property, "volume", 6) == 0)
    {
        char tmpvol[4];
        sprintf(tmpvol, "%d", picoProp_currVolume);
        if (*iosize < strlen(tmpvol)+1)
        {
            *iosize = strlen(tmpvol) + 1;
            return TTS_PROPERTY_SIZE_TOO_SMALL;
        }
        strcpy(value, tmpvol);
        return TTS_SUCCESS;
    }
    else
    {
        LOGE("Unsupported property");
        return TTS_PROPERTY_UNSUPPORTED;
    }
}

/** synthesizeText
 *  synthesizes a text string
 *  @text - text to synthesize
 *  @buffer - buffer which will receive generated samples
 *  @bufferSize - size of buffer
 *  @userdata - pointer to user data which will be passed back to callback function
 *  return tts_result
*/
tts_result TtsEngine::synthesizeText(const char *text, int8_t *buffer, size_t bufferSize, void *userdata)
{
    pico_Char* inp = NULL;
    pico_Char* local_text = NULL;
    short outbuf[MAX_OUTBUF_SIZE/2];
    pico_Int16 bytes_sent, bytes_recv, text_remaining, out_data_type;
    pico_Status ret;
    picoSynthAbort = 0;
    
    if (text == NULL)
    {
        LOGE("synthesizeText called with NULL string");
        return TTS_FAILURE;
    }
    
    if (buffer == NULL)
    {
        LOGE("synthesizeText called with NULL buffer");
        return TTS_FAILURE;
    }
    
    // add property tags to string - if any
    local_text = (pico_Char*)doAddProperties(text);
    if (!local_text)
    {
        LOGE("Failed to allocate memory for text string");
        return TTS_FAILURE;
    }
    
    text_remaining = strlen((const char*)local_text) + 1;
    
    inp = (pico_Char*)local_text;
    
    size_t bufused = 0;
    
    // synthesis loop
    while (text_remaining)
    {
        if (picoSynthAbort)
        {
            ret = pico_resetEngine(picoEngine);
            break;
        }
        
        // feed text into engine
        ret = pico_putTextUtf8(picoEngine, inp, text_remaining, &bytes_sent);
        if (ret != PICO_OK)
        {
            LOGE("Error synthesizing string '%s': [%d]", text, ret);
            if (local_text) free(local_text);
            return TTS_FAILURE;
        }
        
        text_remaining -= bytes_sent;
        inp += bytes_sent;
        do
        {
            if (picoSynthAbort)
            {
                break;
            }
            // retrieve samples and add to buffer
            ret = pico_getData(picoEngine, (void*)outbuf, MAX_OUTBUF_SIZE, &bytes_recv, &out_data_type);
            if (bytes_recv)
            {
                if (bufused + bytes_recv <= bufferSize)
                {
                    memcpy(buffer+bufused, (int8_t*)outbuf, bytes_recv);
                    bufused += bytes_recv;
                }
                else
                {
                    // buffer filled, pass on to callback function
                    int cbret = picoSynthDoneCBPtr(userdata, 16000, AudioSystem::PCM_16_BIT, 1, buffer, bufused, TTS_SYNTH_PENDING);
                    if (cbret == TTS_CALLBACK_HALT)
                    {
                        LOGI("Halt requested by caller. Halting.");
                        picoSynthAbort = 1;
                        break;
                    }
                    bufused = 0;
                    memcpy(buffer, (int8_t*)outbuf, bytes_recv);
                    bufused += bytes_recv;  
                }
            }
        } while (PICO_STEP_BUSY == ret);
        
        // synthesis is finished, notify caller and pass remaining samples
        if (!picoSynthAbort)
        {
            picoSynthDoneCBPtr(userdata, 16000, AudioSystem::PCM_16_BIT, 1, buffer, bufused, TTS_SYNTH_DONE);
        }
        picoSynthAbort = 0;
        
        if (ret != PICO_STEP_IDLE)
        {
            LOGE("Error occurred during synthesis [%d]", ret);
            if (local_text) free(local_text);
            return TTS_FAILURE;
        }
    }
    
    if (local_text) free(local_text);
    return TTS_SUCCESS;
}

/** synthesizeIpa
 *  synthesizes a phonetic string in IPA format
 *  @ipa - phonetic string to synthesize
 *  @buffer - buffer which will receive generated samples
 *  @bufferSize - size of buffer
 *  @userdata - pointer to user data which will be passed back to callback function
 *  return tts_result
*/
tts_result TtsEngine::synthesizeIpa(const char * /*ipa*/, int8_t * /*buffer*/, size_t /*bufferSize*/, void * /*userdata*/)
{
    LOGI("synthIPA not supported in this release");
    return TTS_FEATURE_UNSUPPORTED;
}

/** stop
 *  aborts running synthesis
 *  return tts_result
*/
tts_result TtsEngine::stop()
{
    picoSynthAbort = 1;
    return TTS_SUCCESS;
}

#ifdef __cplusplus
extern "C" {
#endif

TtsEngine* getTtsEngine()
{
    return new TtsEngine();
}

#ifdef __cplusplus
}
#endif

