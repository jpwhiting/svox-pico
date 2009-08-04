/*
 * Copyright (C) 2009 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.svox.pico;

import java.io.File;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;

/*
 * Checks if the voice data for the SVOX Pico Engine is present on the
 * sd card.
 */
public class CheckVoiceData extends Activity {

    // The following constants are the same path constants as the ones defined
    // in external/svox/pico/tts/com_svox_picottsengine.cpp
    private final static String PICO_LINGWARE_PATH = "/sdcard/svox/";
    private final static String PICO_SYSTEM_LINGWARE_PATH = "/system/tts/lang_pico/";

    private final static String[] dataFiles = {
            "de-DE_gl0_sg.bin", "de-DE_ta.bin", "en-GB_kh0_sg.bin", "en-GB_ta.bin",
            "en-US_lh0_sg.bin", "en-US_ta.bin", "es-ES_ta.bin", "es-ES_zl0_sg.bin",
            "fr-FR_nk0_sg.bin", "fr-FR_ta.bin", "it-IT_cm0_sg.bin", "it-IT_ta.bin"
    };

    private final static String[] dataFilesInfo = {
        "deu-DEU", "deu-DEU", "eng-GBR", "eng-GBR", "eng-USA", "eng-USA",
        "spa-ESP", "spa-ESP", "fra-FRA", "fra-FRA", "ita-ITA", "ita-ITA"
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        int result = TextToSpeech.Engine.CHECK_VOICE_DATA_PASS;

        // Check for files
        for (int i = 0; i < dataFiles.length; i++) {
            File tempFile = new File(PICO_LINGWARE_PATH + dataFiles[i]);
            File tempFileSys = new File(PICO_SYSTEM_LINGWARE_PATH + dataFiles[i]);
            if ((!tempFile.exists()) && (!tempFileSys.exists())) {
                result = TextToSpeech.Engine.CHECK_VOICE_DATA_MISSING_DATA;
            }
        }

        // Put the root directory for the sd card data + the data filenames
        Intent returnData = new Intent();
        returnData.putExtra(TextToSpeech.Engine.EXTRA_VOICE_DATA_ROOT_DIRECTORY, PICO_LINGWARE_PATH);
        returnData.putExtra(TextToSpeech.Engine.EXTRA_VOICE_DATA_FILES, dataFiles);
        returnData.putExtra(TextToSpeech.Engine.EXTRA_VOICE_DATA_FILES_INFO, dataFilesInfo);

        setResult(result, returnData);
        finish();
    }

}
