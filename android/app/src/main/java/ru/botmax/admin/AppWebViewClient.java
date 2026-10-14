package ru.botmax.admin;

import android.app.Activity;
import android.graphics.Bitmap;
import android.content.Intent;
import android.net.Uri;
import android.view.View;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ProgressBar;
import android.widget.LinearLayout;

public class AppWebViewClient extends WebViewClient {

    private final Activity activity;
    private final ProgressBar loadingIndicator;
    private final LinearLayout errorView;
    private final WebView webView;

    public AppWebViewClient(Activity activity, WebView webView, ProgressBar loadingIndicator, LinearLayout errorView) {
        this.activity = activity;
        this.webView = webView;
        this.loadingIndicator = loadingIndicator;
        this.errorView = errorView;
    }

    @Override
    public void onPageStarted(WebView view, String url, Bitmap favicon) {
        super.onPageStarted(view, url, favicon);
        if (loadingIndicator != null) {
            loadingIndicator.setVisibility(View.VISIBLE);
        }
    }

    @Override
    public void onPageFinished(WebView view, String url) {
        super.onPageFinished(view, url);
        if (loadingIndicator != null) {
            loadingIndicator.setVisibility(View.GONE);
        }
    }

    @Override
    public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
        if (request != null && request.isForMainFrame()) {
            if (loadingIndicator != null) {
                loadingIndicator.setVisibility(View.GONE);
            }
            if (webView != null) {
                webView.setVisibility(View.GONE);
            }
            if (errorView != null) {
                errorView.setVisibility(View.VISIBLE);
            }
        }
    }

    @Override
    public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
        if (request == null || request.getUrl() == null) {
            return false;
        }
        Uri uri = request.getUrl();
        String scheme = uri.getScheme();
        if (scheme != null && !scheme.equals("http") && !scheme.equals("https")) {
            try {
                Intent intent = new Intent(Intent.ACTION_VIEW, uri);
                activity.startActivity(intent);
                return true;
            } catch (Exception e) {
                return true;
            }
        }
        return false;
    }
}
