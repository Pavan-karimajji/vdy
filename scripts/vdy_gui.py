"""
modules/vdy/scripts/vdy_gui.py

Developer operations GUI for `vdy` - a pure launcher over commands that
already exist (build.bat, conan). Every button shells out; nothing here
reimplements build/publish logic or edits a YAML value - dropdowns are
populated by reading conf/build.yml and CMakePresets.json, never hardcoded.
Subprocess output is NOT captured into the GUI - it's left to inherit this
app's own console (the cmd window gui.bat opened), so there's no in-app log
panel to keep in sync; buttons just show run/done state. Same pattern as
modules/df/scripts/df_gui.py (plan.md item 2) - `vdy` has no CARLA/replay
tooling, so it only gets the two sections that actually apply here.

Workflow, top to bottom:
  1. BUILD & TEST  - build.bat <project> <target> <platform>
  2. PUBLISH       - conan create + upload to the adas-local remote

Run:
    gui.bat
    (or: py vdy_gui.py, from this folder)
"""

import json
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

import yaml

# ── paths ─────────────────────────────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))          # modules/vdy/scripts
VDY_ROOT = os.path.dirname(_THIS_DIR)                             # modules/vdy
SUPERPROJECT_ROOT = os.path.dirname(os.path.dirname(VDY_ROOT))    # up: modules -> root

sys.path.insert(0, os.path.join(SUPERPROJECT_ROOT, "scripts"))
import conan_publish  # noqa: E402 - path must be set up first

PACKAGE_NAME = "adas-vdy"

CONF_DIR = os.path.join(SUPERPROJECT_ROOT, "conf")
VDY_BUILD_YML = os.path.join(VDY_ROOT, "conf", "build.yml")
VDY_CMAKE_PRESETS = os.path.join(VDY_ROOT, "CMakePresets.json")
VDY_CMAKELISTS = os.path.join(VDY_ROOT, "CMakeLists.txt")
GUI_CFG_PATH = os.path.join(_THIS_DIR, "vdy_gui_config.json")


# ── config persistence ────────────────────────────────────────────────────────

def _load_cfg():
    try:
        with open(GUI_CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cfg(**updates):
    cfg = _load_cfg()
    cfg.update(updates)
    try:
        with open(GUI_CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError:
        pass


# ── data helpers (dropdowns - read-only, never edit these files, never
#    hardcoded lists) ─────────────────────────────────────────────────────────

def _list_projects():
    if not os.path.isdir(CONF_DIR):
        return ["base"]
    names = sorted(
        os.path.splitext(f)[0] for f in os.listdir(CONF_DIR) if f.endswith(".yaml")
    )
    return names or ["base"]


def _list_platforms(project):
    try:
        with open(VDY_BUILD_YML, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        platforms = data["variants"][project]["sil"]["platforms"]
        return [p["build"] for p in platforms] or ["vs2026"]
    except (OSError, KeyError, IndexError, TypeError, yaml.YAMLError):
        return ["vs2026"]


def _list_targets():
    """build.bat's valid <target> values aren't listed in any YAML - the
    actual source of truth is which configurePresets exist in
    CMakePresets.json, each named <target>-<platform>."""
    try:
        with open(VDY_CMAKE_PRESETS, encoding="utf-8") as f:
            data = json.load(f)
        names = set()
        for preset in data.get("configurePresets", []):
            if preset.get("hidden"):
                continue
            name = preset.get("name", "")
            if "-" in name:
                names.add(name.split("-", 1)[0])
        return sorted(names) or ["sil", "gtest"]
    except (OSError, json.JSONDecodeError, KeyError):
        return ["sil", "gtest"]


def _current_version():
    """Reads the VERSION currently declared in CMakeLists.txt - the same
    line conanfile.py's set_version() reads, and what `conan create` would
    publish right now if you didn't bump it first."""
    try:
        with open(VDY_CMAKELISTS, encoding="utf-8") as f:
            content = f.read()
        match = re.search(
            r"project\(\s*" + re.escape(PACKAGE_NAME) + r"\s+VERSION\s+([0-9]+\.[0-9]+\.[0-9]+)",
            content, re.IGNORECASE,
        )
        return match.group(1) if match else "?"
    except OSError:
        return "?"


# ── hover tooltips (Tkinter has no built-in widget for this) ──────────────────

class _Tooltip:
    """Small hover tooltip - binds <Enter>/<Leave> on a widget to show/hide a
    borderless Toplevel with a text label near the cursor."""

    def __init__(self, widget, text):
        self._widget = widget
        self._text = text
        self._tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        if self._tip is not None:
            return
        x = self._widget.winfo_rootx() + 10
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self._tip, text=self._text, justify="left", wraplength=340,
                 background="#ffffe0", relief="solid", borderwidth=1,
                 font=("Segoe UI", 8)).pack(ipadx=4, ipady=2)

    def _hide(self, _event=None):
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


# ── subprocess runner ─────────────────────────────────────────────────────────

class _ProcessRunner:
    """Runs one or more commands in sequence on a background thread so the UI
    stays responsive. Output is NOT captured - each command inherits this
    app's own console, same window the user launched gui.bat from. Stops the
    sequence early if a command fails or stop() is called.

    Bug #18: if `cmds` is the editable-aware publish sequence ([editable
    remove, create, upload, editable add]) and stop() lands after the
    `editable remove` has completed but before the final `editable add`
    runs, the package's editable registration would otherwise be left
    removed with no restore - silently breaking the user's own local dev
    loop. _run() detects exactly that condition and runs the restore
    command itself before reporting done; on_done then receives a second
    `editable_restored` arg (True/False) only when this happened, so
    existing single-arg on_done callbacks (build, which never runs an
    editable-aware sequence) are unaffected."""

    def __init__(self, cmds, cwd, on_done=None):
        self._cmds = cmds if isinstance(cmds[0], list) else [cmds]
        self._cwd = cwd
        self._on_done = on_done
        self._proc = None
        self._stopped = False
        self._completed = 0

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stopped = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def _needs_editable_restore(self):
        cmds = self._cmds
        return (
            len(cmds) > 1
            and cmds[0][:3] == ["conan", "editable", "remove"]
            and cmds[-1][:3] == ["conan", "editable", "add"]
            and 0 < self._completed < len(cmds) - 1
        )

    def _run(self):
        rc = 0
        for cmd in self._cmds:
            if self._stopped:
                break
            try:
                self._proc = subprocess.Popen(cmd, cwd=self._cwd)
                rc = self._proc.wait()
            except OSError:
                rc = -1
            if rc != 0:
                break
            self._completed += 1

        restored = None
        if self._stopped and self._needs_editable_restore():
            try:
                restored = subprocess.run(self._cmds[-1], cwd=self._cwd).returncode == 0
            except OSError:
                restored = False

        if self._on_done:
            if restored is not None:
                self._on_done(rc, restored)
            else:
                self._on_done(rc)


# ── main app ──────────────────────────────────────────────────────────────────

class VdyGuiApp:

    def __init__(self, root):
        self.root = root
        root.title("vdy - Developer Operations")
        root.minsize(560, 300)

        self._cfg = _load_cfg()

        self._build_runner = None
        self._publish_runner = None

        self._build_buildtest_section()
        self._build_publish_section()

    # ── BUILD & TEST ──────────────────────────────────────────────────────────

    def _build_buildtest_section(self):
        frame = ttk.LabelFrame(self.root, text="BUILD & TEST", padding=8)
        frame.pack(fill="x", padx=10, pady=(10, 4))

        row1 = ttk.Frame(frame)
        row1.pack(fill="x")
        ttk.Label(row1, text="Project:").pack(side="left")
        self._project = tk.StringVar(value=self._cfg.get("project", "base"))
        project_cb = ttk.Combobox(row1, textvariable=self._project, values=_list_projects(),
                                   state="readonly", width=14)
        project_cb.pack(side="left", padx=(4, 12))
        project_cb.bind("<<ComboboxSelected>>", self._on_project_changed)

        ttk.Label(row1, text="Target:").pack(side="left")
        self._target = tk.StringVar(value=self._cfg.get("target", "sil"))
        target_cb = ttk.Combobox(row1, textvariable=self._target, values=_list_targets(),
                                  state="readonly", width=10)
        target_cb.pack(side="left", padx=(4, 0))

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=(4, 0))
        ttk.Label(row2, text="Platform:").pack(side="left")
        self._platform = tk.StringVar(value=self._cfg.get("platform", "vs2026"))
        self._platform_cb = ttk.Combobox(row2, textvariable=self._platform,
                                          values=_list_platforms(self._project.get()),
                                          state="readonly", width=14)
        self._platform_cb.pack(side="left", padx=(4, 12))

        self._clean = tk.BooleanVar(value=False)
        clean_cb = ttk.Checkbutton(row2, text="clean", variable=self._clean)
        clean_cb.pack(side="left", padx=(0, 12))
        _Tooltip(clean_cb, "Deletes the existing build-<target>-<platform>\n"
                            "folder first, forcing a full rebuild instead of\n"
                            "an incremental one.")

        self._build_run_btn = ttk.Button(row2, text="▶ Build", command=self._run_build)
        self._build_run_btn.pack(side="left")
        self._build_stop_btn = ttk.Button(row2, text="■ Stop", command=self._stop_build,
                                           state="disabled")
        self._build_stop_btn.pack(side="left", padx=4)

        self._build_cmd_label = ttk.Label(frame, text="", foreground="#555",
                                           font=("Consolas", 8))
        self._build_cmd_label.pack(anchor="w", pady=(6, 0))
        self._build_status = ttk.Label(frame, text="idle", foreground="gray")
        self._build_status.pack(anchor="w")

    def _on_project_changed(self, _=None):
        self._platform_cb.config(values=_list_platforms(self._project.get()))
        _save_cfg(project=self._project.get())

    def _run_build(self):
        project, target, platform = self._project.get(), self._target.get(), self._platform.get()
        _save_cfg(project=project, target=target, platform=platform)
        cmd = ["cmd.exe", "/c", "build.bat", project, target, platform] + (
            ["clean"] if self._clean.get() else [])
        self._build_run_btn.config(state="disabled")
        self._build_stop_btn.config(state="normal")
        self._build_cmd_label.config(text="$ " + " ".join(cmd) + f"   (cwd: {VDY_ROOT})")
        self._build_status.config(text="running...", foreground="darkorange")
        self._build_runner = _ProcessRunner(cmd, VDY_ROOT, on_done=self._on_build_done)
        self._build_runner.start()

    def _stop_build(self):
        if self._build_runner:
            self._build_runner.stop()

    def _on_build_done(self, rc):
        self.root.after(0, self._build_done_ui, rc)

    def _build_done_ui(self, rc):
        self._build_run_btn.config(state="normal")
        self._build_stop_btn.config(state="disabled")
        ok = rc == 0
        self._build_status.config(text=f"done (rc={rc})" if ok else f"exited rc={rc}",
                                   foreground="#2a9d2a" if ok else "#c0392b")

    # ── PUBLISH ───────────────────────────────────────────────────────────────

    def _build_publish_section(self):
        frame = ttk.LabelFrame(self.root, text="PUBLISH (adas-local remote)", padding=8)
        frame.pack(fill="x", padx=10, pady=(4, 10))

        row1 = ttk.Frame(frame)
        row1.pack(fill="x")
        ttk.Label(row1, text="Existing versions:").pack(side="left")
        self._pub_existing = tk.StringVar()
        self._pub_existing_cb = ttk.Combobox(row1, textvariable=self._pub_existing,
                                              values=[], state="readonly", width=14)
        self._pub_existing_cb.pack(side="left", padx=4)
        ttk.Button(row1, text="↻", width=3, command=self._refresh_publish_versions).pack(
            side="left")
        self._pub_remote_status = ttk.Label(row1, text="", foreground="gray")
        self._pub_remote_status.pack(side="left", padx=(8, 0))
        _Tooltip(self._pub_existing_cb,
                  "Versions of adas-vdy already on the adas-local remote -\n"
                  "refreshed automatically when this GUI starts. Pick a new\n"
                  "version number below that isn't already in this list.")

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Label(row2, text="Current (CMakeLists.txt):").pack(side="left")
        self._pub_current_label = ttk.Label(row2, text=_current_version(), foreground="#555")
        self._pub_current_label.pack(side="left", padx=(4, 12))

        ttk.Label(row2, text="New version:").pack(side="left")
        self._pub_new_version = tk.StringVar(value=_current_version())
        new_version_entry = ttk.Entry(row2, textvariable=self._pub_new_version, width=10)
        new_version_entry.pack(side="left", padx=4)
        _Tooltip(new_version_entry,
                  "Publishing rewrites this into CMakeLists.txt's\n"
                  "project(adas-vdy VERSION ...) line before running\n"
                  "conan create - the same line conanfile.py's set_version()\n"
                  "already reads. Bumping is a deliberate choice, not\n"
                  "automatic - pick a version not already in the list above.\n"
                  "\n"
                  "Builds EVERY project variant declared in conf/build.yml\n"
                  "(base, cus1, ...) - one conan create per variant, then a\n"
                  "single upload once all of them succeed. This is\n"
                  "deliberate: conan upload has no concept of \"did you build\n"
                  "every configuration\", so publishing only ever builds one\n"
                  "variant would silently leave the others missing on the\n"
                  "remote.")

        self._publish_btn = ttk.Button(row2, text="⬆ Publish", command=self._run_publish)
        self._publish_btn.pack(side="left", padx=(8, 4))
        self._publish_stop_btn = ttk.Button(row2, text="■ Stop", command=self._stop_publish,
                                             state="disabled")
        self._publish_stop_btn.pack(side="left")

        self._publish_cmd_label = ttk.Label(frame, text="", foreground="#555",
                                             font=("Consolas", 8))
        self._publish_cmd_label.pack(anchor="w", pady=(6, 0))
        self._publish_status = ttk.Label(frame, text="idle", foreground="gray")
        self._publish_status.pack(anchor="w")

        self._refresh_publish_versions()

    def _refresh_publish_versions(self):
        # Bug #10: querying the remote used to run synchronously on the main
        # thread (measured ~14s freeze when unreachable) - now backgrounded,
        # same as every other button's _ProcessRunner pattern.
        self._pub_remote_status.config(text="checking remote...", foreground="darkorange")

        def work():
            try:
                versions = conan_publish.list_remote_versions(PACKAGE_NAME)
            except conan_publish.RemoteUnavailableError as exc:
                self.root.after(0, self._on_refresh_versions_done, None, exc)
                return
            self.root.after(0, self._on_refresh_versions_done, versions, None)

        threading.Thread(target=work, daemon=True).start()

    def _on_refresh_versions_done(self, versions, error):
        if error is not None:
            # Bug #9: "can't reach the remote / session expired" must look
            # different from a genuinely empty dropdown, not silently fold
            # into the same "nothing published yet" state.
            self._pub_existing_cb.config(values=[])
            self._pub_remote_status.config(text=f"[remote unreachable] {error}",
                                            foreground="#c0392b")
            return
        self._pub_existing_cb.config(values=versions)
        if versions:
            self._pub_existing_cb.current(len(versions) - 1)
        self._pub_remote_status.config(text="", foreground="gray")

    def _run_publish(self):
        new_version = self._pub_new_version.get().strip()
        if not new_version:
            self._publish_status.config(text="[error] Enter a version number.",
                                         foreground="#c0392b")
            return
        self._publish_btn.config(state="disabled")
        self._publish_status.config(text="checking remote...", foreground="darkorange")

        def work():
            try:
                existing = conan_publish.list_remote_versions(PACKAGE_NAME)
                if new_version in existing:
                    self.root.after(
                        0, self._publish_precheck_failed,
                        f"[error] {PACKAGE_NAME}/{new_version} already exists on the "
                        "remote - pick a different version.")
                    return
                cmds = conan_publish.publish_commands(VDY_ROOT, PACKAGE_NAME, new_version)
            except conan_publish.RemoteUnavailableError as exc:
                self.root.after(0, self._publish_precheck_failed,
                                 f"[error] remote unreachable: {exc}")
                return
            except conan_publish.MissingDependencyError as exc:
                self.root.after(0, self._publish_precheck_failed, f"[error] {exc}")
                return
            self.root.after(0, self._publish_precheck_ok, cmds, new_version)

        threading.Thread(target=work, daemon=True).start()

    def _publish_precheck_failed(self, message):
        self._publish_btn.config(state="normal")
        self._publish_status.config(text=message, foreground="#c0392b")

    def _publish_precheck_ok(self, cmds, new_version):
        try:
            conan_publish.bump_cmake_version(VDY_CMAKELISTS, PACKAGE_NAME, new_version)
        except (OSError, ValueError) as exc:
            self._publish_btn.config(state="normal")
            self._publish_status.config(text=f"[error] {exc}", foreground="#c0392b")
            return
        self._pub_current_label.config(text=_current_version())

        self._publish_stop_btn.config(state="normal")
        self._publish_cmd_label.config(
            text="\n".join("$ " + " ".join(c) for c in cmds) + f"   (cwd: {VDY_ROOT})")
        self._publish_status.config(text="publishing...", foreground="darkorange")
        self._publish_runner = _ProcessRunner(cmds, VDY_ROOT, on_done=self._on_publish_done)
        self._publish_runner.start()

    def _stop_publish(self):
        if self._publish_runner:
            self._publish_runner.stop()

    def _on_publish_done(self, rc, editable_restored=None):
        self.root.after(0, self._publish_done_ui, rc, editable_restored)

    def _publish_done_ui(self, rc, editable_restored=None):
        self._publish_btn.config(state="normal")
        self._publish_stop_btn.config(state="disabled")
        if editable_restored is True:
            self._publish_status.config(
                text="stopped - editable mode restored", foreground="#c0392b")
        elif editable_restored is False:
            self._publish_status.config(
                text="stopped before editable restore - run `conan editable add .` manually",
                foreground="#c0392b")
        else:
            ok = rc == 0
            self._publish_status.config(text=f"done (rc={rc})" if ok else f"exited rc={rc}",
                                         foreground="#2a9d2a" if ok else "#c0392b")
        self._refresh_publish_versions()


def main():
    root = tk.Tk()
    VdyGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
