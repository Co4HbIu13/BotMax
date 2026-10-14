package ru.botmax.admin;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.view.View;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.widget.ProgressBar;

public class AppWebChromeClient extends WebChromeClient {

    private final Activity activity;
    private final ProgressBar loadingIndicator;
    private ValueCallback<Uri[]> fileUploadCallback;

    public AppWebChromeClient(Activity activity, ProgressBar loadingIndicator) {
        this.activity = activity;
        this.loadingIndicator = loadingIndicator;
    }

    @Override
    public void onProgressChanged(WebView view, int newProgress) {
        if (loadingIndicator != null) {
            if (newProgress < 100) {
                loadingIndicator.setVisibility(View.VISIBLE);
                loadingIndicator.setProgress(newProgress);
            } else {
                loadingIndicator.setVisibility(View.GONE);
            }
        }
    }

    @Override
    public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> filePathCallback, FileChooserParams fileChooserParams) {
        if (fileUploadCallback != null) {
            fileUploadCallback.onReceiveValue(null);
        }
        fileUploadCallback = filePathCallback;

        Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("image/*");

        try {
            activity.startActivityForResult(Intent.createChooser(intent, "Выберите изображение приза"), 1001);
            return true;
        } catch (Exception e) {
            fileUploadCallback = null;
            return false;
        }
    }

    public void handleFileResult(int resultCode, Intent data) {
        if (fileUploadCallback != null) {
            Uri[] results = null;
            if (resultCode == Activity.RESULT_OK && data != null) {
                Uri dataUri = data.getData();
                if (dataUri != null) {
                    results = new Uri[]{dataUri};
                }
            }
            fileUploadCallback.onReceiveValue(results);
            fileUploadCallback = null;
        }
    }
}
