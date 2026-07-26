package com.rpgrtl.engine.xenvironment.components;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Process;

import androidx.preference.PreferenceManager;

import com.rpgrtl.engine.box64.Box64Preset;
import com.rpgrtl.engine.box64.Box64PresetManager;
import com.rpgrtl.engine.core.Callback;
import com.rpgrtl.engine.core.DefaultVersion;
import com.rpgrtl.engine.core.EnvVars;
import com.rpgrtl.engine.core.FileUtils;
import com.rpgrtl.engine.core.GeneralComponents;
import com.rpgrtl.engine.core.LocaleHelper;
import com.rpgrtl.engine.core.ProcessHelper;
import com.rpgrtl.engine.widget.LogView;
import com.rpgrtl.engine.xconnector.UnixSocketConfig;
import com.rpgrtl.engine.xenvironment.EnvironmentComponent;
import com.rpgrtl.engine.xenvironment.RootFS;
import com.rpgrtl.shell.ShellLog;

import java.io.File;
import java.util.List;

public class GuestProgramLauncherComponent extends EnvironmentComponent {
    private String guestExecutable;
    private static int pid = -1;
    private EnvVars envVars;
    private File workingDir;
    private String box64Preset = Box64Preset.CONSERVATIVE;
    private Callback<Integer> terminationCallback;
    private boolean deferredStart = false;
    private static final Object lock = new Object();

    /** When true, environment.startEnvironmentComponents() only prepares; call start() again later. */
    public void setDeferredStart(boolean deferredStart) {
        this.deferredStart = deferredStart;
    }

    @Override
    public void start() {
        synchronized (lock) {
            if (deferredStart) {
                // First pass from XEnvironment: extract box64 only, delay wine until XServer is up.
                extractBox64File();
                copyDefaultBox64RCFile();
                deferredStart = false;
                return;
            }
            stop();
            extractBox64File();
            copyDefaultBox64RCFile();
            pid = execGuestProgram();
        }
    }

    @Override
    public void stop() {
        synchronized (lock) {
            if (pid != -1) {
                Process.killProcess(pid);
                pid = -1;
            }
        }
    }

    public Callback<Integer> getTerminationCallback() {
        return terminationCallback;
    }

    public void setTerminationCallback(Callback<Integer> terminationCallback) {
        this.terminationCallback = terminationCallback;
    }

    public String getGuestExecutable() {
        return guestExecutable;
    }

    public void setGuestExecutable(String guestExecutable) {
        this.guestExecutable = guestExecutable;
    }

    public int getPid() {
        return pid;
    }

    public EnvVars getEnvVars() {
        return envVars;
    }

    public void setEnvVars(EnvVars envVars) {
        this.envVars = envVars;
    }

    public File getWorkingDir() {
        return workingDir;
    }

    public void setWorkingDir(File workingDir) {
        this.workingDir = workingDir;
    }

    public String getBox64Preset() {
        return box64Preset;
    }

    public void setBox64Preset(String box64Preset) {
        this.box64Preset = box64Preset;
    }

    private int execGuestProgram() {
        RootFS rootFS = environment.getRootFS();
        File rootDir = rootFS.getRootDir();

        EnvVars envVars = new EnvVars();
        addBox64EnvVars(envVars);
        LocaleHelper.setEnvVars(envVars);

        File box64Bin = new File(rootDir, "/usr/local/bin/box64");
        FileUtils.chmod(box64Bin, 0755);

        // Prefer already-prepared env from WineDisplayActivity (has correct guest paths).
        envVars.put("HOME", rootDir+RootFS.HOME_PATH);
        envVars.put("USER", RootFS.USER);
        envVars.put("TMPDIR", rootDir+"/tmp");
        envVars.put("DISPLAY", ":0");
        envVars.put("PATH", rootDir+rootFS.getWinePath()+"/bin:"+rootDir+"/usr/local/bin:"+rootDir+"/usr/bin");
        envVars.put("LD_LIBRARY_PATH", rootDir+"/usr/lib:"+rootFS.getLibDir().getPath());
        envVars.put("BOX64_LD_LIBRARY_PATH", rootDir+"/lib/x86_64-linux-gnu:"+rootDir+"/usr/lib/x86_64-linux-gnu");
        envVars.put("ANDROID_SYSVSHM_SERVER", rootDir+UnixSocketConfig.SYSVSHM_SERVER_PATH);
        envVars.put("BOX64_LOG", "1");
        envVars.put("BOX64_NOBANNER", "0");
        envVars.put("WINEDEBUG", "-all,+err,+fix");

        if (this.envVars != null) envVars.putAll(this.envVars);

        File shmDir = new File(rootDir, "/tmp/shm");
        if (!shmDir.isDirectory()) shmDir.mkdirs();
        FileUtils.chmod(new File(rootDir, "/tmp"), 0771);

        if (!box64Bin.isFile()) {
            android.util.Log.e("RPGTL-Wine", "box64 missing: " + box64Bin.getAbsolutePath());
            ShellLog.INSTANCE.error(environment.getContext(), "box64 missing: " + box64Bin.getAbsolutePath(), null);
            if (terminationCallback != null) terminationCallback.call(-1);
            return -1;
        }

        // Refuse to exec if INTERP still points at com.winlator (instant silent failure).
        try {
            byte[] head = java.nio.file.Files.readAllBytes(box64Bin.toPath());
            byte[] bad = "/data/data/com.winlator".getBytes(java.nio.charset.StandardCharsets.US_ASCII);
            for (int i = 0; i + bad.length <= head.length; i++) {
                boolean match = true;
                for (int j = 0; j < bad.length; j++) {
                    if (head[i + j] != bad[j]) { match = false; break; }
                }
                if (match) {
                    android.util.Log.e("RPGTL-Wine", "box64 still has com.winlator path — abort exec");
                    ShellLog.INSTANCE.error(environment.getContext(), "box64 still has com.winlator path — abort exec", null);
                    if (terminationCallback != null) terminationCallback.call(-2);
                    return -1;
                }
            }
        } catch (Exception e) {
            android.util.Log.w("RPGTL-Wine", "box64 preflight check failed", e);
        }

        String command = box64Bin.getAbsolutePath() + " " + guestExecutable;
        File processWorkingDir = (workingDir != null && workingDir.isDirectory()) ? workingDir : rootDir;
        android.util.Log.i("RPGTL-Wine", "execGuestProgram: " + command + " cwd=" + processWorkingDir);
        ShellLog.INSTANCE.info(environment.getContext(), "execGuestProgram command=" + command + " cwd=" + processWorkingDir);

        int launchedPid = ProcessHelper.exec(command, envVars, processWorkingDir, (status) -> {
            synchronized (lock) {
                pid = -1;
            }
            android.util.Log.i("RPGTL-Wine", "guest exited status=" + status);
            if (terminationCallback != null) terminationCallback.call(status);
        });
        android.util.Log.i("RPGTL-Wine", "guest pid=" + launchedPid + " box64=" + box64Bin.getAbsolutePath());
        ShellLog.INSTANCE.info(environment.getContext(), "guest pid=" + launchedPid + " box64=" + box64Bin.getAbsolutePath());
        return launchedPid;
    }

    private void extractBox64File() {
        Context context = environment.getContext();
        SharedPreferences preferences = PreferenceManager.getDefaultSharedPreferences(context);
        String box64Version = preferences.getString("box64_version", DefaultVersion.BOX64);
        String currentBox64Version = preferences.getString("current_box64_version", "");

        File box64Bin = new File(environment.getRootFS().getRootDir(), "/usr/local/bin/box64");
        boolean needExtract = !box64Bin.isFile() || box64Bin.length() < 1_000_000L
            || !box64Version.equals(currentBox64Version);
        if (needExtract) {
            GeneralComponents.extractFile(GeneralComponents.Type.BOX64, context, box64Version, DefaultVersion.BOX64);
            preferences.edit().putString("current_box64_version", box64Version).apply();
        }
        FileUtils.chmod(box64Bin, 0755);
        // Always re-patch INTERP: extract bakes /data/data/com.winlator/... into PT_INTERP.
        patchBox64WinlatorPaths(context, box64Bin);
    }

    /**
     * box64 PT_INTERP is /data/data/com.winlator/files/rootfs/lib/ld-linux-aarch64.so.1.
     * Without rewrite, Android execve fails instantly (no stdout, black screen).
     */
    private void patchBox64WinlatorPaths(Context context, File box64Bin) {
        if (box64Bin == null || !box64Bin.isFile()) return;
        try {
            byte[] data = java.nio.file.Files.readAllBytes(box64Bin.toPath());
            byte[] oldP = "/data/data/com.winlator/files/rootfs".getBytes(java.nio.charset.StandardCharsets.US_ASCII);
            String pkg = context.getPackageName();
            // Short bridge files/w must already exist (WinePathCompat.ensureBridge).
            byte[] newP = ("/data/data/" + pkg + "/files/w").getBytes(java.nio.charset.StandardCharsets.US_ASCII);
            if (newP.length > oldP.length) return;
            boolean changed = false;
            for (int i = 0; i <= data.length - oldP.length; i++) {
                boolean match = true;
                for (int j = 0; j < oldP.length; j++) {
                    if (data[i + j] != oldP[j]) { match = false; break; }
                }
                if (!match) continue;
                // Rewrite full C-string: new prefix + old suffix, zero-fill remainder.
                int end = i;
                int maxEnd = Math.min(data.length, i + 512);
                while (end < maxEnd && data[end] != 0) end++;
                int oldFull = end - i;
                int suffixLen = Math.max(0, oldFull - oldP.length);
                int newFull = newP.length + suffixLen;
                if (newFull > oldFull) continue;
                System.arraycopy(newP, 0, data, i, newP.length);
                if (suffixLen > 0) {
                    System.arraycopy(data, i + oldP.length, data, i + newP.length, suffixLen);
                }
                for (int k = i + newFull; k < end + (end < data.length && data[end] == 0 ? 1 : 0); k++) {
                    if (k < data.length) data[k] = 0;
                }
                changed = true;
                i += oldP.length - 1;
            }
            if (changed) {
                java.nio.file.Files.write(box64Bin.toPath(), data);
                FileUtils.chmod(box64Bin, 0755);
                android.util.Log.i("RPGTL-Wine", "box64 INTERP patched for package " + pkg);
            }
            // Ensure ld-linux reachable via lib/
            File root = environment.getRootFS().getRootDir();
            File ld = new File(root, "lib/ld-linux-aarch64.so.1");
            File ldUsr = new File(root, "usr/lib/ld-linux-aarch64.so.1");
            if (!ld.exists() && ldUsr.isFile()) {
                FileUtils.symlink(ldUsr.getAbsolutePath(), ld.getAbsolutePath());
            }
        } catch (Exception e) {
            android.util.Log.e("RPGTL-Wine", "box64 INTERP patch failed", e);
        }
    }

    private void copyDefaultBox64RCFile() {
        Context context = environment.getContext();
        RootFS rootFS = environment.getRootFS();
        FileUtils.copy(context, "winlator/box64/default.box64rc", new File(rootFS.getRootDir(), "/etc/config.box64rc"));
    }

    private void addBox64EnvVars(EnvVars envVars) {
        Context context = environment.getContext();
        RootFS rootFS = environment.getRootFS();
        SharedPreferences preferences = PreferenceManager.getDefaultSharedPreferences(context);
        int box64Logs = preferences.getInt("box64_logs", 0);
        boolean saveToFile = preferences.getBoolean("save_logs_to_file", false);

        envVars.put("BOX64_NOBANNER", box64Logs >= 1 ? "0" : "1");
        envVars.put("BOX64_DYNAREC", "1");
        envVars.put("BOX64_UNITYPLAYER", "0");

        if (box64Logs >= 1) {
            envVars.put("BOX64_LOG", "1");
            envVars.put("BOX64_DYNAREC_MISSING", "1");

            if (box64Logs == 2) {
                envVars.put("BOX64_SHOWSEGV", "1");
                envVars.put("BOX64_DLSYM_ERROR", "1");
                envVars.put("BOX64_TRACE_FILE", "stderr");

                if (saveToFile) {
                    File parent = (new File(preferences.getString("log_file", LogView.getLogFile().getPath()))).getParentFile();
                    if (parent != null && parent.isDirectory()) {
                        File traceDir = new File(parent, "trace");
                        if (!traceDir.isDirectory()) traceDir.mkdirs();
                        FileUtils.clear(traceDir);

                        envVars.put("BOX64_TRACE_FILE", traceDir+"/box64-%pid.txt");
                    }
                }
            }
        }

        envVars.putAll(Box64PresetManager.getEnvVars(context, box64Preset));

        File box64RCFile = new File(rootFS.getRootDir(), "/etc/config.box64rc");
        envVars.put("BOX64_RCFILE", box64RCFile.getPath());
    }

    @Override
    public void onPause() {
        synchronized (lock) {
            if (pid != -1) {
                List<ProcessHelper.PStat> processes = ProcessHelper.getChildProcesses();
                for (int i = processes.size()-1; i >= 0; i--) {
                    ProcessHelper.PStat process = processes.get(i);
                    if (process.guestProcess && process.state != ProcessHelper.PState.STOPPED) {
                        ProcessHelper.suspendProcess(process.pid);
                    }
                }
            }
        }
    }

    @Override
    public void onResume() {
        synchronized (lock) {
            if (pid != -1) {
                List<ProcessHelper.PStat> processes = ProcessHelper.getChildProcesses();
                for (int i = 0; i < processes.size(); i++) {
                    ProcessHelper.PStat process = processes.get(i);
                    if (process.guestProcess && process.state == ProcessHelper.PState.STOPPED) {
                        ProcessHelper.resumeProcess(process.pid);
                    }
                }
            }
        }
    }
}
