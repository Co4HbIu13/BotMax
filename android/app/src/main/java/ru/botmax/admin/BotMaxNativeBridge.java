package ru.botmax.admin;

import android.app.Activity;
import android.content.Context;
import android.os.Build;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.webkit.JavascriptInterface;
import android.widget.Toast;

public class BotMaxNativeBridge {

    private final Activity activity;

    public BotMaxNativeBridge(Activity activity) {
        this.activity = activity;
    }

    @JavascriptInterface
    public void vibrate(int durationMs) {
        try {
            Vibrator v = (Vibrator) activity.getSystemService(Context.VIBRATOR_SERVICE);
            if (v != null && v.hasVibrator()) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    v.vibrate(VibrationEffect.createOneShot(durationMs, VibrationEffect.DEFAULT_AMPLITUDE));
                } else {
                    v.vibrate(durationMs);
                }
            }
        } catch (Exception ignored) {
        }
    }

    @JavascriptInterface
    public void showNativeToast(final String message) {
        activity.runOnUiThread(new ToastRunnable(activity, message));
    }

    private static class ToastRunnable implements Runnable {
        private final Activity activity;
        private final String message;

        public ToastRunnable(Activity activity, String message) {
            this.activity = activity;
            this.message = message;
        }

        @Override
        public void run() {
            Toast.makeText(activity, message, Toast.LENGTH_SHORT).show();
        }
    }
}
