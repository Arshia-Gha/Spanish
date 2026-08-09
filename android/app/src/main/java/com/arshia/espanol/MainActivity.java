package com.arshia.espanol;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.webkit.MimeTypeMap;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.IOException;
import java.io.InputStream;

public class MainActivity extends Activity {
    private static final int REQ_AUDIO = 1001;
    private static final String APP_HOST = "app.local";
    private WebView webView;
    private PermissionRequest pendingAudioRequest;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        setContentView(webView);

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

        webView.setWebViewClient(new LocalAssetClient());
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest request) {
                if (!request.getOrigin().getHost().equals(APP_HOST)) {
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

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_AUDIO && pendingAudioRequest != null) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                pendingAudioRequest.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            } else {
                pendingAudioRequest.deny();
            }
            pendingAudioRequest = null;
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
