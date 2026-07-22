"""
scripts/build_gui.py

Component-agnostic Build & Publish GUI - the build/publish half every
component needs, split out of the old per-component <name>_gui.py so it can
be identical everywhere (plan.md item 17). This file is BYTE-IDENTICAL across
df/vdy/interfaces/shared_config (diff -q == 0), the same invariant
scripts/build.py already holds: nothing component-specific is hardcoded here.

  - the package name is read from this module's conanfile.py at runtime
    (conan_publish.read_package_name), never a per-file constant;
  - the version source (a CMakeLists.txt project() line, or shared_config's
    plain VERSION file) is hidden behind conan_publish.read_current_version /
    bump_version;
  - the project/target/platform dropdowns are driven off `build.py config`
    (the frozen grammar's own discovery output, docs/build_grammar.md §7) -
    one parser, not a private re-parse of conf/build.yml per GUI (plan.md
    item 16).

Pure launcher, same rules as before (plan.md item 2, docs/df_dev_gui_plan.md):
every button shells out to build.bat / conan; nothing here reimplements build
or publish logic or edits a YAML value. Subprocess output is NOT captured into
the GUI - it inherits this app's own console (the cmd window gui.bat opened),
so there is no in-app log panel; buttons just show run/done state.

Speaks the frozen build grammar (plan.md item 14, docs/build_grammar.md):
    build.bat -t <target> -p <platform> [-P <project>] [--clean]

df's CARLA + replay/Foxglove tooling is a separate app now
(scripts/df_sim_gui.py, launched by sim_gui.bat) - it is NOT part of this
common GUI, since only df has it.

Run:
    gui.bat
    (or: py build_gui.py, from this folder)
"""

import json
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

# ── paths ─────────────────────────────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))          # modules/<name>/scripts
MODULE_ROOT = os.path.dirname(_THIS_DIR)                          # modules/<name>
SUPERPROJECT_ROOT = os.path.dirname(os.path.dirname(MODULE_ROOT)) # up: modules -> root

sys.path.insert(0, os.path.join(SUPERPROJECT_ROOT, "scripts"))
import conan_publish  # noqa: E402 - path must be set up first

# Read straight off this module's own conanfile.py so this file stays
# byte-identical across every component (plan.md item 17) - shared_config's
# real name (adas-shared-config) isn't a mechanical transform of its folder,
# so it can't be derived from the directory either.
PACKAGE_NAME = conan_publish.read_package_name(MODULE_ROOT) or os.path.basename(MODULE_ROOT)

BUILD_PY = os.path.join(_THIS_DIR, "build.py")
GUI_CFG_PATH = os.path.join(_THIS_DIR, "build_gui_config.json")

# When nothing is saved yet, land on the sil deliverable rather than whatever
# sorts first alphabetically (gtest) - sil is the more natural first thing to
# build, and this preserves the pre-split GUIs' default.
_PREFERRED_TARGET = "sil"


def _pick(values, current=None):
    """The value to select from `values`: keep `current` if still valid, else
    prefer sil, else the first entry. Keeps the dropdowns from silently
    jumping to an alphabetical accident."""
    if current in values:
        return current
    if _PREFERRED_TARGET in values:
        return _PREFERRED_TARGET
    return values[0]


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


# ── build matrix (dropdowns) ──────────────────────────────────────────────────

def _read_build_matrix():
    """{project: {target: [platform, ...]}} for THIS component, parsed from its
    own `build.py config` output - the single source of truth the frozen
    grammar already prints (docs/build_grammar.md §7), so the GUI never
    re-parses conf/build.yml itself (plan.md item 16). Every config line is
    fully specified (`-t <target> -p <platform> -P <project>`), because the
    grammar makes -t/-p always required - so a target's platform list is read
    per (project, target), never with a hardcoded target key. Returns {} if
    config can't be run, and the dropdowns come up empty rather than the GUI
    failing to open."""
    try:
        result = subprocess.run(
            [sys.executable, BUILD_PY, "config"],
            capture_output=True, text=True, timeout=30, cwd=MODULE_ROOT,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    matrix = {}
    for line in result.stdout.splitlines():
        match = re.search(r"-t\s+(\S+)\s+-p\s+(\S+)\s+-P\s+(\S+)", line)
        if not match:
            continue
        target, platform, project = match.group(1), match.group(2), match.group(3)
        platforms = matrix.setdefault(project, {}).setdefault(target, [])
        if platform not in platforms:
            platforms.append(platform)
    return matrix


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

class BuildGuiApp:

    def __init__(self, root):
        self.root = root
        root.title(f"{PACKAGE_NAME} - Build & Publish")
        root.minsize(560, 300)

        self._cfg = _load_cfg()
        self._matrix = _read_build_matrix()

        self._build_runner = None
        self._publish_runner = None

        self._build_buildtest_section()
        self._build_publish_section()

    # ── BUILD & TEST ──────────────────────────────────────────────────────────

    def _projects(self):
        return sorted(self._matrix) or ["base"]

    def _targets(self, project):
        return sorted(self._matrix.get(project, {})) or ["sil"]

    def _platforms(self, project, target):
        return self._matrix.get(project, {}).get(target) or ["vs2026"]

    def _build_buildtest_section(self):
        frame = ttk.LabelFrame(self.root, text="BUILD & TEST", padding=8)
        frame.pack(fill="x", padx=10, pady=(10, 4))

        row1 = ttk.Frame(frame)
        row1.pack(fill="x")
        ttk.Label(row1, text="Project:").pack(side="left")
        projects = self._projects()
        initial_project = self._cfg.get("project")
        if initial_project not in projects:
            initial_project = projects[0]
        self._project = tk.StringVar(value=initial_project)
        project_cb = ttk.Combobox(row1, textvariable=self._project, values=projects,
                                   state="readonly", width=14)
        project_cb.pack(side="left", padx=(4, 12))
        project_cb.bind("<<ComboboxSelected>>", self._on_project_changed)

        ttk.Label(row1, text="Target:").pack(side="left")
        targets = self._targets(initial_project)
        initial_target = _pick(targets, self._cfg.get("target"))
        self._target = tk.StringVar(value=initial_target)
        self._target_cb = ttk.Combobox(row1, textvariable=self._target, values=targets,
                                        state="readonly", width=10)
        self._target_cb.pack(side="left", padx=(4, 0))
        self._target_cb.bind("<<ComboboxSelected>>", self._on_target_changed)

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=(4, 0))
        ttk.Label(row2, text="Platform:").pack(side="left")
        platforms = self._platforms(initial_project, initial_target)
        initial_platform = self._cfg.get("platform")
        if initial_platform not in platforms:
            initial_platform = platforms[0]
        self._platform = tk.StringVar(value=initial_platform)
        self._platform_cb = ttk.Combobox(row2, textvariable=self._platform,
                                          values=platforms, state="readonly", width=16)
        self._platform_cb.pack(side="left", padx=(4, 12))
        _Tooltip(self._platform_cb,
                  "Only the platforms THIS target actually declares (read from\n"
                  "build.py config, the frozen grammar's own discovery output).\n"
                  "A trailing _debug selects the Debug config; bare is Release.")

        self._clean = tk.BooleanVar(value=False)
        clean_cb = ttk.Checkbutton(row2, text="clean", variable=self._clean)
        clean_cb.pack(side="left", padx=(0, 12))
        _Tooltip(clean_cb, "Passes --clean: deletes this target+platform's\n"
                            "build directory first, forcing a full rebuild\n"
                            "instead of an incremental one.")

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
        project = self._project.get()
        targets = self._targets(project)
        self._target_cb.config(values=targets)
        self._target.set(_pick(targets, self._target.get()))
        self._on_target_changed()
        _save_cfg(project=project)

    def _on_target_changed(self, _=None):
        platforms = self._platforms(self._project.get(), self._target.get())
        self._platform_cb.config(values=platforms)
        if self._platform.get() not in platforms:
            self._platform.set(platforms[0])
        _save_cfg(target=self._target.get())

    def _run_build(self):
        project, target, platform = self._project.get(), self._target.get(), self._platform.get()
        _save_cfg(project=project, target=target, platform=platform)
        cmd = ["cmd.exe", "/c", "build.bat", "-t", target, "-p", platform, "-P", project] + (
            ["--clean"] if self._clean.get() else [])
        self._build_run_btn.config(state="disabled")
        self._build_stop_btn.config(state="normal")
        self._build_cmd_label.config(text="$ " + " ".join(cmd) + f"   (cwd: {MODULE_ROOT})")
        self._build_status.config(text="running...", foreground="darkorange")
        self._build_runner = _ProcessRunner(cmd, MODULE_ROOT, on_done=self._on_build_done)
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
                  f"Versions of {PACKAGE_NAME} already on the adas-local remote -\n"
                  "refreshed automatically when this GUI starts. Pick a new\n"
                  "version number below that isn't already in this list.")

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Label(row2, text="Current version:").pack(side="left")
        self._pub_current_label = ttk.Label(row2, text=conan_publish.read_current_version(MODULE_ROOT),
                                             foreground="#555")
        self._pub_current_label.pack(side="left", padx=(4, 12))

        ttk.Label(row2, text="New version:").pack(side="left")
        self._pub_new_version = tk.StringVar(value=conan_publish.read_current_version(MODULE_ROOT))
        new_version_entry = ttk.Entry(row2, textvariable=self._pub_new_version, width=10)
        new_version_entry.pack(side="left", padx=4)
        _Tooltip(new_version_entry,
                  "Publishing rewrites this component's version at its own\n"
                  "source (a CMakeLists.txt project(...) line, or a plain\n"
                  "VERSION file) before running conan create - the same source\n"
                  "conanfile.py's set_version() already reads. Bumping is a\n"
                  "deliberate choice, not automatic - pick a version not\n"
                  "already in the list above.\n"
                  "\n"
                  "Builds EVERY project variant this component declares - one\n"
                  "conan create per variant, then a single upload once all of\n"
                  "them succeed. This is deliberate: conan upload has no concept\n"
                  "of \"did you build every configuration\", so publishing only\n"
                  "ever one variant would silently leave the others missing on\n"
                  "the remote.")

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
                cmds = conan_publish.publish_commands(MODULE_ROOT, PACKAGE_NAME, new_version)
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
            conan_publish.bump_version(MODULE_ROOT, new_version)
        except (OSError, ValueError) as exc:
            self._publish_btn.config(state="normal")
            self._publish_status.config(text=f"[error] {exc}", foreground="#c0392b")
            return
        self._pub_current_label.config(text=conan_publish.read_current_version(MODULE_ROOT))

        self._publish_stop_btn.config(state="normal")
        self._publish_cmd_label.config(
            text="\n".join("$ " + " ".join(c) for c in cmds) + f"   (cwd: {MODULE_ROOT})")
        self._publish_status.config(text="publishing...", foreground="darkorange")
        self._publish_runner = _ProcessRunner(cmds, MODULE_ROOT, on_done=self._on_publish_done)
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
    BuildGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
