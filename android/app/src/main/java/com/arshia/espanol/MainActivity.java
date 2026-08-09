package com.arshia.espanol;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.media.MediaRecorder;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.util.Base64;
import android.view.WindowInsets;
import android.webkit.JavascriptInterface;
import android.webkit.MimeTypeMap;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final int REQ_AUDIO = 1001;
    private static final String APP_HOST = "app.local";
    private static final int PENDING_NONE = 0;
    private static final int PENDING_SPEECH = 1;
    private static final int PENDING_RECORD = 2;

    private WebView webView;
    private PermissionRequest pendingAudioRequest;
    private SpeechRecognizer speechRecognizer;
    private MediaRecorder mediaRecorder;
    private File audioFile;
    private String pendingSpeechLanguage;
    private int pendingNativeAction = PENDING_NONE;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        webView.setBackgroundColor(0xFFFAF9F6);
        setContentView(webView);

        // Android 15+ draws apps edge-to-edge by default. Keep the web UI out of
        // the status/navigation bars while still using the whole safe content area.
        webView.setOnApplyWindowInsetsListener((view, insets) -> {
            int top;
            int bottom;
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                top = bars.top;
                bottom = bars.bottom;
            } else {
                top = insets.getSystemWindowInsetTop();
                bottom = insets.getSystemWindowInsetBottom();
            }
            view.setPadding(0, top, 0, bottom);
            return insets;
        });

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        if (android.os.Build.VERSION.SDK_INT >= 23) {
            settings.setOffscreenPreRaster(true);
        }

        webView.addJavascriptInterface(new AndroidSpeechBridge(), "AndroidSpeech");
        webView.setWebViewClient(new LocalAssetClient());
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest request) {
                if (request.getOrigin() == null || request.getOrigin().getHost() == null ||
                        !APP_HOST.equals(request.getOrigin().getHost())) {
                    request.deny();
                    return;
                }

                boolean wantsAudio = false;
                for (String resource : request.getResources()) {
                    if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource)) {
                        wantsAudio = true;
                        break;
                    }
                }

                if (!wantsAudio) {
                    request.deny();
                    return;
                }

                runOnUiThread(() -> {
                    if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                        request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                    } else {
                        pendingAudioRequest = request;
                        requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_AUDIO);
                    }
                });
            }
        });

        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState);
        } else {
            webView.loadUrl("https://app.local/index.html");
        }
    }

    private class AndroidSpeechBridge {
        @JavascriptInterface
        public void start(String language) {
            runOnUiThread(() -> startNativeSpeech(language));
        }

        @JavascriptInterface
        public void stop() {
            runOnUiThread(() -> {
                if (speechRecognizer != null) {
                    try { speechRecognizer.stopListening(); } catch (Exception ignored) {}
                }
            });
        }

        @JavascriptInterface
        public void startRecording() {
            runOnUiThread(MainActivity.this::startNativeRecording);
        }

        @JavascriptInterface
        public void stopRecording() {
            runOnUiThread(MainActivity.this::stopNativeRecording);
        }
    }

    private void requestAudioFor(int action) {
        pendingNativeAction = action;
        requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_AUDIO);
    }

    private void startNativeSpeech(String language) {
        pendingSpeechLanguage = normalizeLanguage(language);
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestAudioFor(PENDING_SPEECH);
            return;
        }
        pendingNativeAction = PENDING_NONE;
        beginSpeechRecognition(pendingSpeechLanguage);
    }

    private String normalizeLanguage(String language) {
        if (language == null) return "es-ES";
        String l = language.toLowerCase(Locale.ROOT);
        if (l.startsWith("en")) return "en-US";
        if (l.startsWith("fa")) return "fa-IR";
        return "es-ES";
    }

    private void beginSpeechRecognition(String language) {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            sendSpeechError("unavailable");
            return;
        }

        if (speechRecognizer != null) {
            try { speechRecognizer.destroy(); } catch (Exception ignored) {}
        }

        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
        speechRecognizer.setRecognitionListener(new RecognitionListener() {
            @Override public void onReadyForSpeech(Bundle params) { sendSpeechEvent("ready"); }
            @Override public void onBeginningOfSpeech() { sendSpeechEvent("speech"); }
            @Override public void onRmsChanged(float rmsdB) {}
            @Override public void onBufferReceived(byte[] buffer) {}
            @Override public void onEndOfSpeech() { sendSpeechEvent("end"); }

            @Override
            public void onError(int error) {
                sendSpeechError(String.valueOf(error));
            }

            @Override
            public void onResults(Bundle results) {
                ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                if (matches != null && !matches.isEmpty()) {
                    sendSpeechResult(matches.get(0));
                } else {
                    sendSpeechError("no-match");
                }
            }

            @Override
            public void onPartialResults(Bundle partialResults) {
                ArrayList<String> matches = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                if (matches != null && !matches.isEmpty()) {
                    sendSpeechPartial(matches.get(0));
                }
            }

            @Override public void onEvent(int eventType, Bundle params) {}
        });

        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, language);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, language);
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3);
        speechRecognizer.startListening(intent);
    }

    private void startNativeRecording() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestAudioFor(PENDING_RECORD);
            return;
        }
        pendingNativeAction = PENDING_NONE;
        releaseRecorder();
        try {
            audioFile = new File(getCacheDir(), "conversation-" + System.currentTimeMillis() + ".m4a");
            mediaRecorder = new MediaRecorder();
            mediaRecorder.setAudioSource(MediaRecorder.AudioSource.MIC);
            mediaRecorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            mediaRecorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
            mediaRecorder.setAudioEncodingBitRate(96000);
            mediaRecorder.setAudioSamplingRate(44100);
            mediaRecorder.setOutputFile(audioFile.getAbsolutePath());
            mediaRecorder.prepare();
            mediaRecorder.start();
            sendRecordingEvent("started");
        } catch (Exception e) {
            releaseRecorder();
            sendRecordingError("start-failed");
        }
    }

    private void stopNativeRecording() {
        if (mediaRecorder == null) {
            sendRecordingError("not-recording");
            return;
        }
        try {
            mediaRecorder.stop();
            mediaRecorder.release();
            mediaRecorder = null;
            if (audioFile == null || !audioFile.exists() || audioFile.length() == 0) {
                sendRecordingError("empty-audio");
                return;
            }
            byte[] bytes = readFile(audioFile);
            String base64 = Base64.encodeToString(bytes, Base64.NO_WRAP);
            sendRecordingResult(base64, "audio/mp4");
        } catch (Exception e) {
            sendRecordingError("stop-failed");
        } finally {
            if (audioFile != null) {
                try { audioFile.delete(); } catch (Exception ignored) {}
                audioFile = null;
            }
            releaseRecorder();
        }
    }

    private byte[] readFile(File file) throws IOException {
        try (FileInputStream in = new FileInputStream(file);
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int n;
            while ((n = in.read(buffer)) > 0) out.write(buffer, 0, n);
            return out.toByteArray();
        }
    }

    private void releaseRecorder() {
        if (mediaRecorder != null) {
            try { mediaRecorder.reset(); } catch (Exception ignored) {}
            try { mediaRecorder.release(); } catch (Exception ignored) {}
            mediaRecorder = null;
        }
    }

    private String js(String value) {
        return JSONObject.quote(value == null ? "" : value);
    }

    private void evaluate(String script) {
        runOnUiThread(() -> {
            if (webView != null) webView.evaluateJavascript(script, null);
        });
    }

    private void sendSpeechResult(String text) {
        evaluate("window.__nativeSpeechResult&&window.__nativeSpeechResult(" + js(text) + ");");
    }

    private void sendSpeechPartial(String text) {
        evaluate("window.__nativeSpeechPartial&&window.__nativeSpeechPartial(" + js(text) + ");");
    }

    private void sendSpeechError(String error) {
        evaluate("window.__nativeSpeechError&&window.__nativeSpeechError(" + js(error) + ");");
    }

    private void sendSpeechEvent(String event) {
        evaluate("window.__nativeSpeechEvent&&window.__nativeSpeechEvent(" + js(event) + ");");
    }

    private void sendRecordingResult(String base64, String mime) {
        evaluate("window.__nativeRecordingResult&&window.__nativeRecordingResult(" + js(base64) + "," + js(mime) + ");");
    }

    private void sendRecordingError(String error) {
        evaluate("window.__nativeRecordingError&&window.__nativeRecordingError(" + js(error) + ");");
    }

    private void sendRecordingEvent(String event) {
        evaluate("window.__nativeRecordingEvent&&window.__nativeRecordingEvent(" + js(event) + ");");
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_AUDIO) return;

        boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;

        if (pendingAudioRequest != null) {
            if (granted) {
                pendingAudioRequest.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            } else {
                pendingAudioRequest.deny();
            }
            pendingAudioRequest = null;
        }

        int action = pendingNativeAction;
        pendingNativeAction = PENDING_NONE;
        if (!granted) {
            if (action == PENDING_RECORD) sendRecordingError("permission-denied");
            else if (action == PENDING_SPEECH) sendSpeechError("permission-denied");
            return;
        }

        if (action == PENDING_SPEECH) {
            beginSpeechRecognition(pendingSpeechLanguage == null ? "es-ES" : pendingSpeechLanguage);
        } else if (action == PENDING_RECORD) {
            startNativeRecording();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        releaseRecorder();
        if (speechRecognizer != null) {
            try { speechRecognizer.destroy(); } catch (Exception ignored) {}
            speechRecognizer = null;
        }
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
        }
        super.onDestroy();
    }

    private class LocalAssetClient extends WebViewClient {
        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            if (!APP_HOST.equals(request.getUrl().getHost())) {
                return super.shouldInterceptRequest(view, request);
            }

            String path = request.getUrl().getPath();
            if (path == null || path.equals("/") || path.isEmpty()) {
                path = "/index.html";
            }
            if (path.contains("..")) {
                return new WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden", null,
                        new java.io.ByteArrayInputStream(new byte[0]));
            }

            String assetPath = "www" + path;
            try {
                InputStream stream = getAssets().open(assetPath);
                return new WebResourceResponse(mimeType(path), "UTF-8", stream);
            } catch (IOException ignored) {
                return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", null,
                        new java.io.ByteArrayInputStream(new byte[0]));
            }
        }

        private String mimeType(String path) {
            String ext = MimeTypeMap.getFileExtensionFromUrl(path);
            String mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
            if (mime != null) return mime;
            if (path.endsWith(".json")) return "application/json";
            if (path.endsWith(".js")) return "application/javascript";
            if (path.endsWith(".css")) return "text/css";
            if (path.endsWith(".svg")) return "image/svg+xml";
            return "application/octet-stream";
        }
    }
}
