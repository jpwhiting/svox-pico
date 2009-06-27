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
/* speaking rate    */
#define PICO_DEF_RATE       100
#define PICO_MAX_RATE       500
#define PICO_MIN_PITCH      50
/* speaking pitch   */
#define PICO_DEF_PITCH      100
#define PICO_MAX_PITCH      200
#define PICO_MIN_VOLUME     0
/* speaking volume  */
#define PICO_DEF_VOLUME     400
#define PICO_MAX_VOLUME     500
/* string constants */
#define MAX_OUTBUF_SIZE     128
const char* PICO_LINGWARE_PATH              = "/sdcard/svox/";
const char* PICO_VOICE_NAME                 = "PicoVoice";
const char* PICO_SPEED_OPEN_TAG             = "<speed level='%d'>";
const char* PICO_SPEED_CLOSE_TAG            = "</speed>";
const char* PICO_PITCH_OPEN_TAG             = "<pitch level='%d'>";
const char* PICO_PITCH_CLOSE_TAG            = "</pitch>";
const char* PICO_VOLUME_OPEN_TAG            = "<volume level='%d'>";
const char* PICO_VOLUME_CLOSE_TAG           = "</volume>";
const char* PICO_PHONEME_OPEN_TAG           = "<phoneme ph=\"%s\">";

/* supported voices     */
const char* picoSupportedLangIso3[]         = { "eng",               "eng",               "deu",               "spa",               "fra",               "ita" };
const char* picoSupportedCountryIso3[]      = { "USA",               "GBR",               "DEU",               "ESP",               "FRA",               "ITA" };
const char* picoSupportedLang[]             = { "en-rUS",           "en-rGB",           "de-rDE",           "es-rES",           "fr-rFR",           "it-rIT" };
const char* picoInternalLang[]              = { "en-US",            "en-GB",            "de-DE",            "es-ES",            "fr-FR",            "it-IT" };
const char* picoInternalTaLingware[]        = { "en-US_ta.bin",     "en-GB_ta.bin",     "de-DE_ta.bin",     "es-ES_ta.bin",     "fr-FR_ta.bin",     "it-IT_ta.bin" };
const char* picoInternalSgLingware[]        = { "en-US_lh0_sg.bin", "en-GB_kh0_sg.bin", "de-DE_gl0_sg.bin", "es-ES_zl0_sg.bin", "fr-FR_nk0_sg.bin", "it-IT_cm0_sg.bin" };
const char* picoInternalUtppLingware[]      = { "en-US_utpp.bin",   "en-GB_utpp.bin",   "de-DE_utpp.bin",   "es-ES_utpp.bin",   "fr-FR_utpp.bin",   "it-IT_utpp.bin" };
const int picoNumSupportedLang              = 6;

/* supported properties */
const char* picoSupportedProperties[]       = { "language", "rate", "pitch", "volume" };
const int picoNumSupportedProperties        = 4;


/* adapation layer global variables */
synthDoneCB_t* picoSynthDoneCBPtr;
void* picoMemArea = NULL;
pico_System     picoSystem = NULL;
pico_Resource   picoTaResource = NULL;
pico_Resource   picoSgResource = NULL;
pico_Resource   picoUtppResource = NULL;
pico_Engine     picoEngine = NULL;
pico_Char* picoTaFileName = NULL;
pico_Char* picoSgFileName = NULL;
pico_Char* picoUtppFileName = NULL;
pico_Char* picoTaResourceName = NULL;
pico_Char* picoSgResourceName = NULL;
pico_Char* picoUtppResourceName = NULL;
int     picoSynthAbort = 0;
char*   picoProp_currLang   = NULL;                 /* current language */
int     picoProp_currRate   = PICO_DEF_RATE;        /* current rate     */
int     picoProp_currPitch  = PICO_DEF_PITCH;       /* current pitch    */
int     picoProp_currVolume = PICO_DEF_VOLUME;      /* current volume   */

int picoCurrentLangIndex = -1;


/* internal helper functions */

/** checkForLanguage
 *  Check if the requested language is among the supported languages.
 *  @language -  the language to check, either in xx or xx-rYY format
 *  return index of the language, or -1 if not supported.
*/
static int checkForLanguage( const char * language )
{
     int found = -1;                                         /* language not found   */

    /* Verify that the requested locale is a locale that we support.    */
    for (int i = 0; i < picoNumSupportedLang; i++)
    {
        if (strcmp(language, picoSupportedLang[i]) == 0)
        {
            found = i;
            break;
        }
    };
    if (found < 0)
    {
        /* We didn't find an exact match; it may have been specified with only the first 2 characters.
           This could overmatch ISO 639-3 language codes.                                   */
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
    };
    return found;
}


/** cleanResources
 *  Unloads any loaded Pico resources.
*/
static void cleanResources( void )
{
    if (picoEngine)
    {
        pico_disposeEngine( picoSystem, &picoEngine );
        pico_releaseVoiceDefinition(picoSystem, (pico_Char*)PICO_VOICE_NAME);
        picoEngine = NULL;
    }
    if (picoUtppResource)
    {
        pico_unloadResource( picoSystem, &picoUtppResource );
        picoUtppResource = NULL;
    }
    if (picoTaResource)
    {
        pico_unloadResource( picoSystem, &picoTaResource );
        picoTaResource = NULL;
    }
    if (picoSgResource)
    {
        pico_unloadResource( picoSystem, &picoSgResource );
        picoSgResource = NULL;
    }
    picoCurrentLangIndex = -1;
}


/** cleanFiles
 *  Frees any memory allocated for file and resource strings.
*/
static void cleanFiles( void )
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

/** hasResourcesForLanguage
 *  Check to see if the resources required to load the language at the specified index
 *  are properly installed
 *  @langIndex - the index of the language to check the resources for. The index is valid.
 *  return true if the required resources are installed, false otherwise
 */
static bool hasResourcesForLanguage(int langIndex) {
    FILE * pFile;
    char* fileName = (char*)malloc(PICO_MAX_DATAPATH_NAME_SIZE + PICO_MAX_FILE_NAME_SIZE);
    
    strcpy((char*)fileName, PICO_LINGWARE_PATH);
    strcat((char*)fileName, (const char*)picoInternalTaLingware[langIndex]);
    pFile = fopen(fileName,"r");
    if (pFile == NULL){
        free(fileName);
        return false;
    } else {
        fclose (pFile);
    }

    strcpy((char*)fileName, PICO_LINGWARE_PATH);
    strcat((char*)fileName, (const char*)picoInternalSgLingware[langIndex]);
    pFile = fopen(fileName, "r");
    if (pFile == NULL) {
        free(fileName);
        return false;
    } else {
        fclose(pFile);
        free(fileName);
        return true;
    }
}

/** doLanguageSwitchFromLangIndex
 *  Switch to requested language. If language is already loaded it returns
 *  immediately, if another language is loaded this will first be unloaded
 *  and the new one then loaded. If no language is loaded the requested will be loaded.
 *  @langIndex -  the index of the language to load, which is guaranteed to be supported.
 *  return TTS_SUCCESS or TTS_FAILURE
 */
static tts_result doLanguageSwitchFromLangIndex(int langIndex)
{
    // if we already have a loaded language, check if it's the same one as requested
    if (picoProp_currLang && (strcmp(picoProp_currLang, picoSupportedLang[langIndex]) == 0))
    {
        LOGI("Language already loaded (%s == %s)", picoProp_currLang, picoSupportedLang[langIndex]);
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
        LOGE("Failed to load textana resource for %s [%d]", picoSupportedLang[langIndex], ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }

    // load signal generation Lingware resource file
    ret = pico_loadResource(picoSystem, picoSgFileName, &picoSgResource);
    if (PICO_OK != ret)
    {
        LOGE("Failed to load siggen resource for %s [%d]", picoSupportedLang[langIndex], ret);
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
        LOGE("Failed to load utpp resource for %s [%d]", picoSupportedLang[langIndex], ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }

    // Get text analysis resource name
    ret = pico_getResourceName(picoSystem, picoTaResource, (char*)picoTaResourceName);
    if (PICO_OK != ret)
    {
        LOGE("Failed to get textana resource name for %s [%d]", picoSupportedLang[langIndex], ret);
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
            LOGE("Failed to get utpp resource name for %s [%d]", picoSupportedLang[langIndex], ret);
            cleanResources();
            cleanFiles();
            return TTS_FAILURE;
        }
    }
    if (PICO_OK != ret)
    {
        LOGE("Failed to get siggen resource name for %s [%d]", picoSupportedLang[langIndex], ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }

    // create a voice definition
    ret = pico_createVoiceDefinition(picoSystem, (const pico_Char*)PICO_VOICE_NAME);
    if (PICO_OK != ret)
    {
        LOGE("Failed to create voice for %s [%d]", picoSupportedLang[langIndex], ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }

    // add text analysis resource to voice
    ret = pico_addResourceToVoiceDefinition(picoSystem, (const pico_Char*)PICO_VOICE_NAME, picoTaResourceName);
    if (PICO_OK != ret)
    {
        LOGE("Failed to add textana resource to voice for %s [%d]", picoSupportedLang[langIndex], ret);
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
            LOGE("Failed to add utpp resource to voice for %s [%d]", picoSupportedLang[langIndex], ret);
            cleanResources();
            cleanFiles();
            return TTS_FAILURE;
        }
    }

    if (PICO_OK != ret)
    {
        LOGE("Failed to add siggen resource to voice for %s [%d]", picoSupportedLang[langIndex], ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }

    ret = pico_newEngine(picoSystem, (const pico_Char*)PICO_VOICE_NAME, &picoEngine);
    if (PICO_OK != ret)
    {
        LOGE("Failed to create engine for %s [%d]", picoSupportedLang[langIndex], ret);
        cleanResources();
        cleanFiles();
        return TTS_FAILURE;
    }

    strcpy(picoProp_currLang, picoSupportedLang[langIndex]);
    picoCurrentLangIndex = langIndex;

    LOGI("loaded %s successfully", picoProp_currLang);

    return TTS_SUCCESS;
}

/** doLanguageSwitch
 *  Switch to requested language. If language is already loaded it returns
 *  immediately, if another language is loaded this will first be unloaded
 *  and the new one then loaded. If no language is loaded the requested will be loaded.
 *  @language -  the language to check, either in xx or xx-rYY format (i.e "en" or "en-rUS")
 *  return TTS_SUCCESS or TTS_FAILURE
*/
static tts_result doLanguageSwitch(const char* language)
{
    // load new language
    int langIndex = checkForLanguage(language);
    if (langIndex < 0)
    {
        LOGE("Tried to swith to non-supported language %s", language);
        return TTS_FAILURE;
    }
    LOGI("Found supported language %s", picoSupportedLang[langIndex]);

    return doLanguageSwitchFromLangIndex( langIndex );
}

/** doAddProperties
 *  Add <speed>, <pitch> and <volume> tags to text, if the properties have been set to non-default values,
 *  and return the new string.  The calling function is responsible for freeing the returned string.
 *  @str - text to apply tags to
 *  return new string with tags applied
*/
static char* doAddProperties(const char* str)
{
    char* data = NULL;
    int haspitch = 0, hasspeed = 0, hasvol = 0;
    int textlen = strlen(str) + 1;

    if (picoProp_currPitch != PICO_DEF_PITCH)           /* non-default pitch    */
    {
        textlen += strlen(PICO_PITCH_OPEN_TAG) + 5;
        textlen += strlen(PICO_PITCH_CLOSE_TAG);
        haspitch = 1;
    }
    if (picoProp_currRate != PICO_DEF_RATE)             /* non-default rate     */
    {
        textlen += strlen(PICO_SPEED_OPEN_TAG) + 5;
        textlen += strlen(PICO_SPEED_CLOSE_TAG);
        hasspeed = 1;
    }
    if (picoProp_currVolume != PICO_DEF_VOLUME)         /* non-default volume   */
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
    memset(data, 0, textlen);                           /* clear it             */
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
 *  Allocates Pico memory block and initializes Pico system.
 *  synthDoneCBPtr - Pointer to callback function which will receive generated samples
 *  return tts_result
*/
tts_result TtsEngine::init( synthDoneCB_t synthDoneCBPtr )
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
    
    picoCurrentLangIndex = -1;
    
    return TTS_SUCCESS;
}


/** shutdown
 *  Unloads all Pico resources; terminates Pico system and frees Pico memory block.
 *  return tts_result
*/
tts_result TtsEngine::shutdown( void )
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

/** isLanguageAvailable
 *  Returns the level of support for a language.
 *  @lang - string with ISO 3 letter language code.
 *  @country - string with ISO 3 letter country code .
 *  @variant - string with language variant for that language and country pair.
 *  return tts_support_result
*/
tts_support_result TtsEngine::isLanguageAvailable(const char *lang, const char *country,
            const char *variant) {
    int langIndex = -1;
    int countryIndex = -1;
    //-------------------------
    // language matching
    // if no language specified
    if (lang == NULL)  {
        LOGE("TtsEngine::isLanguageAvailable called with no language");
        return TTS_LANG_NOT_SUPPORTED;
    }

    // find a match on the language
    for (int i = 0; i < picoNumSupportedLang; i++)
    {
        if (strcmp(lang, picoSupportedLangIso3[i]) == 0) {
            langIndex = i;
            break;
        }
    }
    if (langIndex < 0) {
        // language isn't supported
        LOGV("TtsEngine::isLanguageAvailable called with unsupported language");
        return TTS_LANG_NOT_SUPPORTED;
    }

    //-------------------------
    // country matching
    // if no country specified
    if ((country == NULL) || (strlen(country) == 0)) {
        // check installation of matched language
        return (hasResourcesForLanguage(langIndex) ? TTS_LANG_AVAILABLE : TTS_LANG_MISSING_DATA);
    }
    
    // find a match on the country
    for (int i = langIndex; i < picoNumSupportedLang; i++) {
        if ((strcmp(lang, picoSupportedLangIso3[i]) == 0)
                && (strcmp(country, picoSupportedCountryIso3[i]) == 0)) {
            countryIndex = i;
            break;
        }
    }
    if (countryIndex < 0)  {
        // we didn't find a match on the country, but we had a match on the language
        // check installation of matched language
        return (hasResourcesForLanguage(langIndex) ? TTS_LANG_AVAILABLE : TTS_LANG_MISSING_DATA);
    } else {
        // we have a match on the language and the country
        langIndex = countryIndex;
        // check installation of matched language + country
        return (hasResourcesForLanguage(langIndex) ? TTS_LANG_COUNTRY_AVAILABLE : TTS_LANG_MISSING_DATA);
    }
   
    // no variants supported in this library, TTS_LANG_COUNTRY_VAR_AVAILABLE cannot be returned.
}

/** loadLanguage
 *  Load a new language.
 *  @lang - string with ISO 3 letter language code.
 *  @country - string with ISO 3 letter country code .
 *  @variant - string with language variant for that language and country pair.
 *  return tts_result
*/
tts_result TtsEngine::loadLanguage(const char *lang, const char *country, const char *variant)
{
    return TTS_FAILURE;
    //return setProperty("language", value, size);
}

/** setLanguage
 *  Load a new language.
 *  @lang - string with ISO 3 letter language code.
 *  @country - string with ISO 3 letter country code .
 *  @variant - string with language variant for that language and country pair.
 *  return tts_result
 */
tts_result TtsEngine::setLanguage(const char *lang, const char *country, const char *variant) {
    if (lang == NULL) {
        LOGE("TtsEngine::setLanguage called with NULL language");
        return TTS_FAILURE;
    }

    // we look for a match on the language first
    // then we look for a match on the country.
    // if no match on the language:
    //       return an error
    // if match on the language, but no match on the country:
    //       load the language found for the language match
    // if match on the language, and match on the country:
    //       load the language found for the country match

    // find a match on the language
    int langIndex = -1;
    for (int i = 0; i < picoNumSupportedLang; i++)
    {
        if (strcmp(lang, picoSupportedLangIso3[i]) == 0) {
            langIndex = i;
            break;
        }
    }
    if (langIndex < 0) {
        // language isn't supported
        LOGE("TtsEngine::setLanguage called with unsupported language");
        return TTS_FAILURE;
    }

    // find a match on the country
    if (country != NULL) {
        int countryIndex = -1;
        for (int i = langIndex; i < picoNumSupportedLang; i++) {
            if ((strcmp(lang, picoSupportedLangIso3[i]) == 0)
                    && (strcmp(country, picoSupportedCountryIso3[i]) == 0)) {
                countryIndex = i;
                break;
            }
        }

        if (countryIndex < 0)  {
            // we didn't find a match on the country, but we had a match on the language,
            // use that language
            LOGI("TtsEngine::setLanguage found matching language(%s) but not matching country(%s).",
                    lang, country);
        } else {
            // we have a match on the language and the country
            langIndex = countryIndex;
        }
    }

    return doLanguageSwitchFromLangIndex( langIndex );
}


/** getLanguage
 *  Get the currently loaded language - if any.
 *  @lang - string with current ISO 3 letter language code, empty string if no loaded language.
 *  @country - string with current ISO 3 letter country code, empty string if no loaded language.
 *  @variant - string with current language variant, empty string if no loaded language.
 *  return tts_result
*/
tts_result TtsEngine::getLanguage(char *language, char *country, char *variant)
{
    if (picoCurrentLangIndex == -1) {
        strcpy(language, "\0");
        strcpy(country, "\0");
        strcpy(variant, "\0");
    } else {
        strncpy(language, picoSupportedLangIso3[picoCurrentLangIndex], 3);
        strncpy(country, picoSupportedCountryIso3[picoCurrentLangIndex], 3);
        // no variant in this implementation
        strcpy(variant, "\0");
    }
    return TTS_SUCCESS;
}


/** setAudioFormat
 * sets the audio format to use for synthesis, returns what is actually used.
 * @encoding - reference to encoding format
 * @rate - reference to sample rate
 * @channels - reference to number of channels
 * return tts_result
 * */
tts_result TtsEngine::setAudioFormat(AudioSystem::audio_format& encoding, uint32_t& rate,
            int& channels)
{
    // ignore the input parameters, the enforced audio parameters are fixed here
    encoding = AudioSystem::PCM_16_BIT;
    rate = 16000;
    channels = 1;
    return TTS_SUCCESS;
}


/** setProperty
 *  Set property. The supported properties are:  language, rate, pitch and volume.
 *  @property - name of property to set
 *  @value - value to set
 *  @size - size of value
 *  return tts_result
*/
tts_result TtsEngine::setProperty( const char * property, const char * value, const size_t size )
{
    /* Sanity check */
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
 *  Get the property.  Supported properties are:  language, rate, pitch and volume.
 *  @property - name of property to get
 *  @value - buffer which will receive value of property
 *  @iosize - size of value - if size is too small on return this will contain actual size needed
 *  return tts_result
*/
tts_result TtsEngine::getProperty(const char *property, char *value, size_t* iosize)
{
    /* sanity check */
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
 *  Synthesizes a text string.
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

    /* Add property tags to the string - if any.    */
    local_text = (pico_Char*)doAddProperties(text);
    if (!local_text)
    {
        LOGE("Failed to allocate memory for text string");
        return TTS_FAILURE;
    }

    text_remaining = strlen((const char*)local_text) + 1;

    inp = (pico_Char*)local_text;

    size_t bufused = 0;

    /* synthesis loop   */
    while (text_remaining)
    {
        if (picoSynthAbort)
        {
            ret = pico_resetEngine(picoEngine);
            break;
        }

        /* Feed the text into the engine.   */
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
            /* Retrieve the samples and add them to the buffer. */
            ret = pico_getData(picoEngine, (void*)outbuf, MAX_OUTBUF_SIZE, &bytes_recv, &out_data_type);
            if (bytes_recv)
            {
                if ((bufused + bytes_recv) <= bufferSize)
                {
                    memcpy(buffer+bufused, (int8_t*)outbuf, bytes_recv);
                    bufused += bytes_recv;
                }
                else
                {
                    /* The buffer filled; pass this on to the callback function.    */
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

        /* The synthesis is finished; notify the caller and pass the remaining samples.
           Use 16 KHz, 16-bit samples.                                              */
        if (!picoSynthAbort)
        {
            picoSynthDoneCBPtr( userdata, 16000, AudioSystem::PCM_16_BIT, 1, buffer, bufused, TTS_SYNTH_DONE);
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
 *  Synthesizes a phonetic string in IPA format.
 *  @ipa - phonetic string to synthesize
 *  @buffer - buffer which will receive generated samples
 *  @bufferSize - size of buffer
 *  @userdata - pointer to user data which will be passed back to callback function
 *  return tts_result
*/
tts_result TtsEngine::synthesizeIpa( const char * ipa, int8_t * buffer, size_t bufferSize, void * userdata )
{
    pico_Char*  inp = NULL;
    pico_Char*  local_text = NULL;
    short       outbuf[MAX_OUTBUF_SIZE/2];
    pico_Int16  bytes_sent, bytes_recv, text_remaining, out_data_type;
    pico_Status ret;

    picoSynthAbort = 0;
    if (ipa == NULL)
    {
        LOGE("synthesizeIpa called with NULL string");
        return TTS_FAILURE;
    }

    if (buffer == NULL)
    {
        LOGE("synthesizeIpa called with NULL buffer");
        return TTS_FAILURE;
    }

    /* Append phoneme tag. %%%
       <phoneme ph="xxx"/>  */

    /* Add property tags to the string - if any.    */
    local_text = (pico_Char*)doAddProperties( ipa );
    if (!local_text)
    {
        LOGE("Failed to allocate memory for text string");
        return TTS_FAILURE;
    }

    text_remaining = strlen((const char*)local_text) + 1;

    inp = (pico_Char*)local_text;

    size_t bufused = 0;

    /* synthesis loop   */
    while (text_remaining)
    {
        if (picoSynthAbort)
        {
            ret = pico_resetEngine( picoEngine );
            break;
        }

        /* Feed the text into the engine.   */
        ret = pico_putTextUtf8( picoEngine, inp, text_remaining, &bytes_sent );
        if (ret != PICO_OK)
        {
            LOGE("Error synthesizing string '%s': [%d]", ipa, ret);
            if (local_text) free(local_text);
            return TTS_FAILURE;
        }

        /* Process the remaining string.    */
        text_remaining -= bytes_sent;
        inp += bytes_sent;
        do
        {
            if (picoSynthAbort)
            {
                break;
            }
            /* Retrieve the samples and add them to the buffer. */
            ret = pico_getData( picoEngine, (void*)outbuf, MAX_OUTBUF_SIZE, &bytes_recv, &out_data_type );
            if (bytes_recv)
            {
                if ((bufused + bytes_recv) <= bufferSize)
                {
                    memcpy(buffer+bufused, (int8_t*)outbuf, bytes_recv);
                    bufused += bytes_recv;
                }
                else
                {
                    /* The buffer filled; pass this on to the callback function.    */
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

        /* The synthesis is finished; notify the caller and pass the remaining samples.
           Use 16 KHz, 16-bit samples.                                              */
        if (!picoSynthAbort)
        {
            picoSynthDoneCBPtr( userdata, 16000, AudioSystem::PCM_16_BIT, 1, buffer, bufused, TTS_SYNTH_DONE );
        }
        picoSynthAbort = 0;                 /* succeeded    */

        if (ret != PICO_STEP_IDLE)
        {
            LOGE("Error occurred during synthesis [%d]", ret);
            if (local_text) free(local_text);
            return TTS_FAILURE;
        }
    }

    if (local_text)
        free(local_text);
    return TTS_SUCCESS;             /* succeeded    */
}


/** stop
 *  Aborts the running synthesis.
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

