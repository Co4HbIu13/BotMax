package ru.botmax.admin;

import android.app.Activity;
import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
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

    @JavascriptInterface
    public void showNotification(final String title, final String message, final String orderId) {
        try {
            NotificationManager nm = (NotificationManager) activity.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) return;

            Intent intent = new Intent(activity, MainActivity.class);
            intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            intent.putExtra("order_id", orderId);

            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                flags |= PendingIntent.FLAG_IMMUTABLE;
            }
            PendingIntent pendingIntent = PendingIntent.getActivity(activity, 0, intent, flags);

            Notification.Builder builder;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                builder = new Notification.Builder(activity, MainActivity.NOTIFICATION_CHANNEL_ID);
            } else {
                builder = new Notification.Builder(activity);
                builder.setPriority(Notification.PRIORITY_HIGH);
            }

            builder.setContentTitle(title)
                   .setContentText(message)
                   .setSmallIcon(R.drawable.ic_launcher)
                   .setAutoCancel(true)
                   .setContentIntent(pendingIntent)
                   .setDefaults(Notification.DEFAULT_ALL);

            int notifId = (orderId != null && !orderId.isEmpty()) ? Math.abs(orderId.hashCode()) : 1001;
            nm.notify(notifId, builder.build());

            // Also trigger vibration
            vibrate(300);
        } catch (Exception ignored) {
        }
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
