package ru.botmax.admin;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

public class MainActivity extends Activity implements View.OnClickListener {

    public static final String PREFS_NAME = "BotMaxPrefs";
    public static final String KEY_SERVER_URL = "server_url";
    public static final String DEFAULT_URL = "https://anussai.duckdns.org/admin";
    public static final int FILE_CHOOSER_REQUEST_CODE = 1001;

    private WebView webView;
    private ProgressBar loadingIndicator;
    private LinearLayout errorView;
    private Button btnRetry;
    private Button btnSettings;
    private AppWebChromeClient chromeClient;
    private boolean doubleBackToExitPressedOnce;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        doubleBackToExitPressedOnce = false;
        prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);

        webView = (WebView) findViewById(R.id.webView);
        loadingIndicator = (ProgressBar) findViewById(R.id.loadingIndicator);
        errorView = (LinearLayout) findViewById(R.id.errorView);
        btnRetry = (Button) findViewById(R.id.btnRetry);
        btnSettings = (Button) findViewById(R.id.btnSettings);

        setupWebView();

        if (btnRetry != null) {
            btnRetry.setOnClickListener(this);
        }
        if (btnSettings != null) {
            btnSettings.setOnClickListener(this);
        }

        loadAdminUrl();
    }

    private void setupWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        }

        String customUserAgent = settings.getUserAgentString() + " BotMAX-Admin-Android/1.0.0";
        settings.setUserAgentString(customUserAgent);

        webView.addJavascriptInterface(new BotMaxNativeBridge(this), "BotMaxAndroid");
        webView.setWebViewClient(new AppWebViewClient(this, webView, loadingIndicator, errorView));

        chromeClient = new AppWebChromeClient(this, loadingIndicator);
        webView.setWebChromeClient(chromeClient);
    }

    public void loadAdminUrl() {
        String url = prefs.getString(KEY_SERVER_URL, DEFAULT_URL);
        if (webView != null) {
            webView.loadUrl(url);
        }
    }

    public void showServerSettingsDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle(getString(R.string.server_settings_title));

        final EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setText(prefs.getString(KEY_SERVER_URL, DEFAULT_URL));
        input.setSelection(input.getText().length());
        builder.setView(input);

        builder.setPositiveButton(getString(R.string.btn_save), new SaveServerDialogListener(this, input));
        builder.setNegativeButton(getString(R.string.btn_cancel), new CancelDialogListener());
        builder.setNeutralButton(getString(R.string.btn_reset_default), new ResetServerDialogListener(this));

        builder.show();
    }

    @Override
    public void onClick(View v) {
        if (v == null) {
            return;
        }
        if (v.getId() == R.id.btnRetry) {
            if (errorView != null) {
                errorView.setVisibility(View.GONE);
            }
            if (webView != null) {
                webView.setVisibility(View.VISIBLE);
            }
            loadAdminUrl();
        } else if (v.getId() == R.id.btnSettings) {
            showServerSettingsDialog();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQUEST_CODE && chromeClient != null) {
            chromeClient.handleFileResult(resultCode, data);
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }

        if (doubleBackToExitPressedOnce) {
            super.onBackPressed();
            return;
        }

        this.doubleBackToExitPressedOnce = true;
        Toast.makeText(this, getString(R.string.exit_prompt), Toast.LENGTH_SHORT).show();

        new Handler(Looper.getMainLooper()).postDelayed(new ResetBackTask(this), 2000);
    }

    public void resetBackPressed() {
        doubleBackToExitPressedOnce = false;
    }

    public SharedPreferences getAppPrefs() {
        return prefs;
    }

    public WebView getAppWebView() {
        return webView;
    }

    public LinearLayout getAppErrorView() {
        return errorView;
    }

    private static class ResetBackTask implements Runnable {
        private final MainActivity activity;

        public ResetBackTask(MainActivity activity) {
            this.activity = activity;
        }

        @Override
        public void run() {
            if (activity != null) {
                activity.resetBackPressed();
            }
        }
    }

    private static class CancelDialogListener implements DialogInterface.OnClickListener {
        @Override
        public void onClick(DialogInterface dialog, int which) {
            if (dialog != null) {
                dialog.cancel();
            }
        }
    }

    private static class SaveServerDialogListener implements DialogInterface.OnClickListener {
        private final MainActivity activity;
        private final EditText input;

        public SaveServerDialogListener(MainActivity activity, EditText input) {
            this.activity = activity;
            this.input = input;
        }

        @Override
        public void onClick(DialogInterface dialog, int which) {
            if (activity == null || input == null) {
                return;
            }
            String newUrl = input.getText().toString().trim();
            if (!newUrl.isEmpty()) {
                if (!newUrl.startsWith("http://") && !newUrl.startsWith("https://")) {
                    newUrl = "https://" + newUrl;
                }
                activity.getAppPrefs().edit().putString(KEY_SERVER_URL, newUrl).apply();
                if (activity.getAppErrorView() != null) {
                    activity.getAppErrorView().setVisibility(View.GONE);
                }
                if (activity.getAppWebView() != null) {
                    activity.getAppWebView().setVisibility(View.VISIBLE);
                    activity.getAppWebView().loadUrl(newUrl);
                }
                Toast.makeText(activity, "Адрес сохранен", Toast.LENGTH_SHORT).show();
            }
        }
    }

    private static class ResetServerDialogListener implements DialogInterface.OnClickListener {
        private final MainActivity activity;

        public ResetServerDialogListener(MainActivity activity) {
            this.activity = activity;
        }

        @Override
        public void onClick(DialogInterface dialog, int which) {
            if (activity == null) {
                return;
            }
            activity.getAppPrefs().edit().putString(KEY_SERVER_URL, DEFAULT_URL).apply();
            if (activity.getAppErrorView() != null) {
                activity.getAppErrorView().setVisibility(View.GONE);
            }
            if (activity.getAppWebView() != null) {
                activity.getAppWebView().setVisibility(View.VISIBLE);
                activity.getAppWebView().loadUrl(DEFAULT_URL);
            }
            Toast.makeText(activity, "Сброшено на сервер по умолчанию", Toast.LENGTH_SHORT).show();
        }
    }
}
