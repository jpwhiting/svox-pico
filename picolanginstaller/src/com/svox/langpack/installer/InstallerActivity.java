package com.svox.langpack.installer;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

import android.app.Activity;
import android.content.Intent;
import android.content.res.AssetFileDescriptor;
import android.content.res.Resources;
import android.net.Uri;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.util.Log;
import android.view.View;
import android.view.View.OnClickListener;
import android.widget.Button;

public class InstallerActivity extends Activity {
    private static final int DATA_ROOT_DIRECTORY_REQUEST_CODE = 42;
    private String rootDirectory = "";

    /** Called when the activity is first created. */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Intent getRootDirectoryIntent = new Intent();
        getRootDirectoryIntent.setClassName("com.svox.pico", "com.svox.pico.CheckVoiceData");
        startActivityForResult(getRootDirectoryIntent, DATA_ROOT_DIRECTORY_REQUEST_CODE);
    }

    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data){
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == DATA_ROOT_DIRECTORY_REQUEST_CODE) {
            rootDirectory = data.getStringExtra(TextToSpeech.Engine.EXTRA_VOICE_DATA_ROOT_DIRECTORY);
            runInstaller();
        }
    }

    private void runInstaller(){
        try {
            Resources res = getResources();
            AssetFileDescriptor langPackFd = res
                    .openRawResourceFd(R.raw.svoxlangpack);
            InputStream stream = langPackFd.createInputStream();

            (new Thread(new unzipper(stream))).start();
        } catch (IOException e) {
            Log.e("PicoLangInstaller", "Unable to open langpack resource.");
            e.printStackTrace();
        }
        setContentView(R.layout.installing);
    }

    private void uninstall() {
        Intent intent = new Intent(Intent.ACTION_DELETE);
        String packageName = getPackageName();
        Uri data = Uri.fromParts("package", packageName, null);
        intent.setData(data);
        startActivity(intent);
    }

    private boolean unzipLangPack(InputStream stream) {
        FileOutputStream out;
        byte buf[] = new byte[16384];
        try {
            ZipInputStream zis = new ZipInputStream(stream);
            ZipEntry entry = zis.getNextEntry();
            while (entry != null) {
                if (entry.isDirectory()) {
                    File newDir = new File(rootDirectory + entry.getName());
                    newDir.mkdir();
                } else {
                    String name = entry.getName();
                    File outputFile = new File(rootDirectory + name);
                    String outputPath = outputFile.getCanonicalPath();
                    name = outputPath
                            .substring(outputPath.lastIndexOf("/") + 1);
                    outputPath = outputPath.substring(0, outputPath
                            .lastIndexOf("/"));
                    File outputDir = new File(outputPath);
                    outputDir.mkdirs();
                    outputFile = new File(outputPath, name);
                    outputFile.createNewFile();
                    out = new FileOutputStream(outputFile);

                    int numread = 0;
                    do {
                        numread = zis.read(buf);
                        if (numread <= 0) {
                            break;
                        } else {
                            out.write(buf, 0, numread);
                        }
                    } while (true);
                    out.close();
                }
                entry = zis.getNextEntry();
            }
            return true;
        } catch (IOException e) {
            e.printStackTrace();
            return false;
        }
    }

    public class unzipper implements Runnable {
        public InputStream stream;

        public unzipper(InputStream is) {
            stream = is;
        }

        public void run() {
            boolean succeeded = unzipLangPack(stream);
            if (succeeded) {
                runOnUiThread(new uninstallDisplayer());
            } else {
                runOnUiThread(new retryDisplayer());
            }
        }
    }

    public class uninstallDisplayer implements Runnable {
        public void run() {
            setContentView(R.layout.uninstall);
            Button uninstallButton = (Button) findViewById(R.id.uninstallButton);
            uninstallButton.setOnClickListener(new OnClickListener() {
                public void onClick(View arg0) {
                    uninstall();
                }
            });
        }
    }

    public class retryDisplayer implements Runnable {
        public void run() {
            setContentView(R.layout.retry);
            Button retryButton = (Button) findViewById(R.id.retryButton);
            retryButton.setOnClickListener(new OnClickListener() {
                public void onClick(View arg0) {
                    runInstaller();
                }
            });
        }
    }

}
