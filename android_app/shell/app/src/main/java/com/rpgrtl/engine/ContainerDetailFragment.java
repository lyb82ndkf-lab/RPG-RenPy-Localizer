package com.rpgrtl.engine;

import android.view.View;
import android.widget.Spinner;

/**
 * Compatibility shell for dialog code copied from Winlator. RPGTL does not use
 * Winlator's container editor UI, so these methods intentionally return safe
 * defaults.
 */
public final class ContainerDetailFragment {
    private ContainerDetailFragment() {}

    public static void loadScreenSizeSpinner(View view, String value) {}

    public static void createWinComponentsTab(View view, String value) {}

    public static String getScreenSize(View view) {
        return "1280x720";
    }

    public static String getWinComponents(View view) {
        return "";
    }

    public static void loadScreenSizeSpinner(Spinner spinner, String value) {}
}
