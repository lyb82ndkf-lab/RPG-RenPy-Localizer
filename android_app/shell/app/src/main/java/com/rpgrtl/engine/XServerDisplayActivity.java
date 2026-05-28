package com.rpgrtl.engine;

import androidx.appcompat.app.AppCompatActivity;
import androidx.preference.PreferenceManager;

import com.rpgrtl.engine.container.Container;
import com.rpgrtl.engine.contentdialog.DebugDialog;
import com.rpgrtl.engine.core.Callback;
import com.rpgrtl.engine.core.EnvVars;
import com.rpgrtl.engine.widget.InputControlsView;
import com.rpgrtl.engine.widget.TouchpadView;
import com.rpgrtl.engine.widget.XServerView;
import com.rpgrtl.engine.winhandler.WinHandler;
import com.rpgrtl.engine.xenvironment.RootFS;
import com.rpgrtl.engine.xenvironment.XEnvironment;
import com.rpgrtl.engine.xserver.XServer;

/**
 * Minimal RPGTL-owned host activity shape required by the transplanted
 * Winlator runtime classes. WineDisplayActivity will extend this and fill these
 * fields while keeping RPGTL as the app shell.
 */
public abstract class XServerDisplayActivity extends AppCompatActivity {
    protected XServer xServer;
    protected XServerView xServerView;
    protected TouchpadView touchpadView;
    protected InputControlsView inputControlsView;
    protected WinHandler winHandler;
    protected XEnvironment environment;
    protected RootFS rootFS;
    protected String screenEffectProfile;
    protected Container container;
    protected EnvVars overrideEnvVars = new EnvVars();
    protected com.rpgrtl.engine.xserver.ScreenInfo screenInfo;
    protected String dxWrapper = Container.DEFAULT_DXWRAPPER;
    protected String winComponents = Container.DEFAULT_WINCOMPONENTS;
    protected DebugDialog debugDialog;

    public XServer getXServer() {
        return xServer;
    }

    public XServerView getXServerView() {
        return xServerView;
    }

    public TouchpadView getTouchpadView() {
        return touchpadView;
    }

    public InputControlsView getInputControlsView() {
        return inputControlsView;
    }

    public WinHandler getWinHandler() {
        return winHandler;
    }

    public XEnvironment getEnvironment() {
        return environment;
    }

    public RootFS getRootFS() {
        return rootFS;
    }

    public String getScreenEffectProfile() {
        return screenEffectProfile;
    }

    public void setScreenEffectProfile(String screenEffectProfile) {
        this.screenEffectProfile = screenEffectProfile;
    }

    public android.content.SharedPreferences getPreferences() {
        return PreferenceManager.getDefaultSharedPreferences(this);
    }

    public DebugDialog getDebugDialog() {
        return debugDialog;
    }

    public Container getContainer() {
        return container;
    }

    public void setContainer(Container container) {
        this.container = container;
    }

    public EnvVars getOverrideEnvVars() {
        return overrideEnvVars;
    }

    public com.rpgrtl.engine.xserver.ScreenInfo getScreenInfo() {
        return screenInfo != null ? screenInfo : (xServer != null ? xServer.screenInfo : null);
    }

    public void setScreenInfo(com.rpgrtl.engine.xserver.ScreenInfo screenInfo) {
        this.screenInfo = screenInfo;
    }

    public void setDXWrapper(String dxWrapper) {
        this.dxWrapper = dxWrapper;
    }

    public String getDXWrapper() {
        return dxWrapper;
    }

    public void setWinComponents(String winComponents) {
        this.winComponents = winComponents;
    }

    public String getWinComponents() {
        return winComponents;
    }

    public void setOpenFileCallback(Callback<android.net.Uri> callback) {
        // RPGTL does not use Winlator's internal file picker. Kept for copied helpers.
    }
}
