#!/usr/bin/env python3
"""Common build orchestrator - plan.md item 10
(docs/build_conanfile_commonization_plan.md), speaking the frozen argument
grammar of plan.md item 14 (docs/build_grammar.md).

Physically identical across every component in this repo (df, vdy, sil_host,
perception-core, interfaces, shared_config) - the only thing that differs
between components is their own conf/build.yml. No component name or kind may
ever become a code branch here; a real behavioral difference belongs in
conf/build.yml as layout_kind/package_id_extra, or as a component's own real
target keys under variants.<project> (§2.1a), not in this file. Propagating a
future fix means re-copying this file into every component's scripts/ by hand -
an accepted cost (docs/build_conanfile_commonization_plan.md, "Core
philosophy").

Grammar (plan.md item 14, docs/build_grammar.md) - four axes, two of them
never inferred:

    python build.py -t <target> -p <platform> [-P <project>] [--clean]

  -t/--target    REQUIRED. A target key under variants.<project> in this
                 component's own conf/build.yml (sil, gtest, coverage, docs,
                 prod, package).
  -p/--platform  REQUIRED. One of that target's own platforms: entries
                 (vs2026, ubuntu_gcc, aarch64_qcc_qnx, tda4_ti, noarch;
                 a trailing _debug suffix selects the debug config).
  -P/--project   Optional, defaults to base.

-t and -p are deliberately mandatory even when conf/build.yml leaves only one
possible value. A first-in-list default would make the YAML's list *order*
load-bearing - reordering two platform lines would silently change what
`-t gtest` builds - and `-t gtest` must never quietly mean "whichever compiler
happens to be listed first". Same reasoning as the reference convention
bricks/cem200/generic/vs2017/btest/GENERIC, which names both axes explicitly.
Platform-independent targets (docs) declare the frozen token `noarch` and are
still typed out, so there is no exception to the rule.

--build-dir (plan.md item 14) relocates the build directory without this file
knowing anything about superprojects: the superproject's own root build.py
passes a folder under its ws/ here when it delegates, so a root-invoked build
lands in <superproject>/ws/ while a directly-invoked one stays in this module's
own directory and a standalone clone keeps working with no superproject
present. Defaulted, it reproduces exactly the pre-item-14 paths.

package_kind (library/application/data) used to be a per-component field,
removed entirely 2026-07-20 (plan.md item 10's own follow-up finding): it
was never read differently anywhere except conanfile.py's layout(), which
now branches on Conan's own self.package_type instead. shared_config (the
one component that used to short-circuit here as package_kind: data) now
has a real CMakeLists.txt/build()/package() and goes through the exact
same conan install -> cmake --preset -> cmake --build sequence as
everyone else - zero component branches left in this file.

Target discovery (revised 2026-07-20, §0.3/§2.1a/§7a): there is no
targets: metadata field. Every real target is its own key directly under
variants.<project>, each carrying its own platforms: list (reused via a
YAML anchor/alias where identical) - the same shape a proven external
reference (mf_trjpla.yaml) uses for its own production/testing/
documentation build kinds. target_blocks() below discovers valid targets
straight from those keys - nothing to keep in sync by hand.

Usage: python build.py -t <target> -p <platform> [-P <project>] [--clean]
       python build.py config
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent  # modules/<name>/

# Targets whose post-build step differs from a plain configure+build. Keyed on
# the target NAME only - never on the component - so this stays the same file
# in every module (docs/build_grammar.md §3).
TEST_TARGETS = ("gtest", "coverage")


# Open log file for this run, or None before one has been opened / when logging
# is off. Module-level rather than threaded through every call because run() is
# invoked from several places and the log is a property of the whole invocation,
# not of one command (plan.md item 18).
_LOG = None


def log(text=""):
    """Print to the console AND to the run's log file. Console output is never
    sacrificed for the log - watching a build live is the common case, and
    losing that would be a regression (plan.md item 18)."""
    print(text)
    if _LOG is not None:
        _LOG.write(text + "\n")
        _LOG.flush()


def open_log(log_dir, name):
    """<log_dir>/<name>.log. For a directly-invoked module build log_dir is
    <build-dir>/logs (inside the build tree, so --clean takes it along); the
    superproject overrides it via --log-dir to a central ws/logs so every
    build's log sits in one place instead of scattered inside each build tree.

    <name> is the relocated build directory's own folder name when the
    superproject passes --build-dir (so a ws/ log is self-identifying, e.g.
    df-base-sil-vs2026.log rather than a generic sil-vs2026.log every module
    would share), and <target>-<platform> for a directly-invoked module build
    (unchanged pre-item-14 behavior - the module directory you're already in
    identifies it). See main().

    Truncated per run, not appended or timestamped: one file per build holding
    the most recent run. Chosen deliberately over keeping history - it never
    grows and never needs pruning."""
    global _LOG
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{name}.log"
    _LOG = open(path, "w", encoding="utf-8", errors="replace")
    return path


def close_log():
    global _LOG
    if _LOG is not None:
        _LOG.close()
        _LOG = None


def run(cmd, cwd):
    """Run a child process, streaming its output to the console and the log at
    the same time. The child's own output is the whole point - a failing build
    prints its real error from conan/cmake/ctest, not from this script - so it
    is captured rather than inherited. Note the side effect: because stdout is
    a pipe rather than a console, child tools drop ANSI colour and may batch
    their output slightly differently than when run by hand."""
    log(" ".join(str(c) for c in cmd))
    proc = subprocess.Popen(
        cmd, cwd=str(cwd),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    for line in proc.stdout:
        log(line.rstrip("\n"))
    proc.wait()
    if proc.returncode != 0:
        log(f"\nFAILED (exit {proc.returncode}): {' '.join(str(c) for c in cmd)}")
        close_log()
        sys.exit(proc.returncode)


def rmtree_if_exists(path):
    if path.exists():
        print(f"Cleaning {path} ...")
        shutil.rmtree(path)


def check_conan_installed():
    if shutil.which("conan") is None:
        sys.exit("ERROR: Conan is not installed or not in PATH.")


def warn_if_stale_profile():
    profile = Path.home() / ".conan2" / "profiles" / "default"
    if not profile.is_file():
        return
    lines = profile.read_text(encoding="utf-8").splitlines()
    if not any(line.startswith("compiler=") for line in lines):
        print("WARNING: No C++ compiler entry found in the Conan default profile.")
        print("If Visual Studio is already installed, this may just be a stale")
        print("profile - continuing anyway. The conan install step below will")
        print("report the real error if a toolchain genuinely cannot be found.")


def load_conf():
    conf_path = ROOT / "conf" / "build.yml"
    return yaml.safe_load(conf_path.read_text(encoding="utf-8"))


def declared_first_party(conf, project):
    """This component's own first-party (adas-*) requires: for <project>, read
    straight off its conf/build.yml. Logged at the top of every build so a log
    says up front what it depended on, before the conan/cmake output (plan.md
    item 18 follow-up). Only the DECLARED set is known here, before conan
    install runs; each dependency's resolved source (Editable/Download/Cache) is
    Conan's to decide and prints lower in this same log."""
    variant = (conf.get("variants") or {}).get(project, {})
    return [ref for ref in variant.get("requires", []) if ref.startswith("adas-")]


def target_blocks(project_conf):
    """Every key under variants.<project> that is a mapping containing a
    platforms: list is a real, declared target (§2.1a) - no separate
    targets: field to keep in sync; the YAML's own keys are the list."""
    return {
        key: value["platforms"]
        for key, value in (project_conf or {}).items()
        if isinstance(value, dict) and "platforms" in value
    }


def platform_names(platforms):
    """The platform tokens of one target's platforms: list, in declaration
    order. Order is presentational only - it never selects anything, since
    -p is mandatory (see this module's docstring)."""
    return [entry["build"] for entry in platforms]


def package_ref():
    """This component's own "<name>/<version>" Conan reference, read straight
    out of its conanfile.py - used only by the `package` target. Never derived
    from the directory name, same reason the superproject's own build.py
    doesn't: at least one component (shared_config -> adas-shared-config)
    isn't a mechanical transform of its folder."""
    text = (ROOT / "conanfile.py").read_text(encoding="utf-8")
    name = re.search(r'\bname\s*=\s*"([^"]+)"', text)
    version = re.search(r'\bversion\s*=\s*"([^"]+)"', text)
    if not name or not version:
        sys.exit("ERROR: could not read name/version from conanfile.py")
    return f"{name.group(1)}/{version.group(1)}"


def print_config(conf):
    """python build.py config - lists every real command this component
    accepts, read straight off conf/build.yml's own target keys
    (target_blocks(), §2.1a), with zero requires:/tool_requires:
    dependency-chain expansion (that's Conan's job at install time, not this
    listing's - docs/build_conanfile_commonization_plan.md §4.3). Every line
    is fully specified - -t and -p are always present, because they're always
    required (plan.md item 14)."""
    variants = conf.get("variants", {}) or {}

    for project, project_conf in variants.items():
        for target, platforms in target_blocks(project_conf).items():
            for platform in platform_names(platforms):
                print(f"python build.py -t {target} -p {platform} -P {project}")


def main():
    if sys.argv[1:] == ["config"]:
        print_config(load_conf())
        return

    p = argparse.ArgumentParser(
        description="Build one target of this component (docs/build_grammar.md)")
    p.add_argument("-P", "--project", default="base",
                   help="Project name (default: base) - selects the variants.<project> block")
    p.add_argument("-t", "--target", required=True,
                   help="Target to build (sil/gtest/coverage/docs/prod/package) - never inferred")
    p.add_argument("-p", "--platform", required=True,
                   help="Toolchain+arch token (vs2026/ubuntu_gcc/aarch64_qcc_qnx/tda4_ti/noarch) - never inferred")
    p.add_argument("--clean", action="store_true",
                   help="Remove this target+platform's build directory first")
    p.add_argument("--build-dir", default=None,
                   help="Where to build (default: <module>/build-<target>-<platform>)")
    p.add_argument("--log-dir", default=None,
                   help="Where to write the log (default: <build-dir>/logs). The superproject "
                        "points this at its central ws/logs so every build's log sits in one place, "
                        "not scattered inside each build tree.")
    p.add_argument("--no-log", action="store_true",
                   help="Don't write a log file (console output only)")
    p.add_argument("--upload", action="store_true",
                   help="package target only: also `conan upload` after `conan create`")
    args = p.parse_args()

    conf = load_conf()
    layout_kind = conf.get("layout_kind", "output_folder")

    project_conf = (conf.get("variants") or {}).get(args.project, {})
    blocks = target_blocks(project_conf)
    if args.target not in blocks:
        sys.exit(f"ERROR: unknown target '{args.target}' - valid: {sorted(blocks)}")

    # Platform is validated per TARGET, not per component: a component may well
    # build sil for vs2026+qnx but gtest for vs2026 only, and asking for the
    # qnx gtest must fail rather than quietly build something else.
    valid_platforms = platform_names(blocks[args.target])
    if args.platform not in valid_platforms:
        sys.exit(f"ERROR: unknown platform '{args.platform}' for target "
                 f"'{args.target}' - valid: {sorted(valid_platforms)}")

    check_conan_installed()
    warn_if_stale_profile()

    build_type = "Debug" if args.platform.endswith("_debug") else "Release"
    requested_dir = Path(args.build_dir).resolve() if args.build_dir else None

    # Resolved once, here, because the log lives inside the build directory and
    # therefore has to be known before anything runs. cmake_layout lets Conan
    # append its own "build" under the output base; output_folder names the
    # directory directly.
    if layout_kind == "cmake_layout":
        output_base = requested_dir or ROOT
        build_dir = output_base / "build"
    else:
        output_base = None
        build_dir = requested_dir or (ROOT / f"build-{args.target}-{args.platform}")

    # --clean wipes the build tree, and the logs with it - so clean BEFORE
    # opening the log, or a clean build's first act is deleting its own log
    # file (plan.md item 18).
    if args.clean:
        rmtree_if_exists(build_dir)

    # Log filename: the relocated build's own folder name when --build-dir is
    # given (so every superproject ws/ log is self-identifying, e.g.
    # df-base-sil-vs2026.log, distinct from every other module's build), else
    # the plain <target>-<platform> a directly-invoked module has always used.
    # Log directory: --log-dir when the superproject asks for a central ws/logs,
    # otherwise inside this build's own tree (unchanged standalone behavior).
    log_name = requested_dir.name if requested_dir else f"{args.target}-{args.platform}"
    log_dir = Path(args.log_dir).resolve() if args.log_dir else (build_dir / "logs")
    log_path = None
    if not args.no_log:
        log_path = open_log(log_dir, log_name)

    # Declared dependency set at the very top, before the first build step, so
    # the log is self-documenting about what it depended on (plan.md item 18
    # follow-up). Same set a GUI shows as --with candidates via the root
    # build.py's `deps` command.
    deps = declared_first_party(conf, args.project)
    log(f"First-party dependencies (conf/build.yml requires:, project={args.project}):")
    for ref in deps:
        log(f"  - {ref}")
    if not deps:
        log("  (none)")
    log("")

    try:
        _build(args, layout_kind, build_type, output_base, build_dir)
    finally:
        if log_path is not None:
            print(f"\nLog written to {log_path}")
        close_log()


def _build(args, layout_kind, build_type, output_base, build_dir):
    if args.target == "package":
        # conan create builds and packages through Conan's own flow - no
        # preset/build-folder involved at all, so it shares none of the
        # configure+build path below.
        run(["conan", "create", ".", "--build=missing",
             "-o", f"project={args.project}", "-s", f"build_type={build_type}"], cwd=ROOT)
        if args.upload:
            run(["conan", "upload", package_ref(), "-r", "adas-local", "--confirm"], cwd=ROOT)
        else:
            log(f"\nPackaged {package_ref()} into the local Conan cache. "
                f"Pass --upload to publish it to adas-local.")
        return

    if args.target == "docs":
        doxyfile = ROOT / "Doxyfile"
        if not doxyfile.is_file():
            sys.exit(f"ERROR: target 'docs' declared in conf/build.yml but no Doxyfile at {doxyfile}")
        build_dir.mkdir(parents=True, exist_ok=True)
        run(["doxygen", str(doxyfile)], cwd=ROOT)
        log(f"\nDocs generated for project: {args.project}")
        return

    # Discarded before EVERY build, whatever the layout_kind, and not only on
    # --clean: Conan APPENDS an include: entry to this file for each output
    # folder it has ever generated into, and every one of those includes
    # defines presets named "conan-default"/"conan-release". Once a second
    # distinct --build-dir has been used, CMake refuses to read the file at all
    # - "Could not read presets ...: Duplicate preset: conan-default" - which
    # kills even a `cmake --preset sil-vs2026` that never wanted the Conan
    # presets, because CMake parses CMakeUserPresets.json before resolving any
    # preset name. This bites output_folder and cmake_layout modules alike (hit
    # for real on shared_config and sil_host, both output_folder). The file is
    # generated and gitignored, and the conan install below regenerates it with
    # exactly the one include for this run, so dropping it is self-healing.
    (ROOT / "CMakeUserPresets.json").unlink(missing_ok=True)

    if layout_kind == "cmake_layout":
        # Conan owns the folder layout here and generates the presets itself,
        # so --build-dir is honored by handing Conan that folder as its output
        # base and letting cmake_layout append its own "build" underneath - the
        # generated presets then already point at the right place, and
        # overriding -B would only fight them. Undefaulted, output_base is ROOT
        # and this reproduces exactly the pre-item-14 paths.
        install_cmd = ["conan", "install", ".", "--output-folder", str(output_base),
                        "--update", "--build=missing",
                        "-s", f"build_type={build_type}"]
        configure_cmd = ["cmake", "--preset", "conan-default",
                         f"-DADAS_PROJECT={args.project}"]
        build_cmd = ["cmake", "--build", "--preset", "conan-release"]
        test_cmd = ["ctest", "--preset", "conan-release"]
    else:  # output_folder
        # The hand-written CMakePresets.json hardcodes
        # binaryDir/CMAKE_TOOLCHAIN_FILE under ${sourceDir}, so relocating the
        # build means overriding both on the command line - verified live that
        # -B wins over a preset's own binaryDir. The preset is still what
        # supplies the generator/architecture/toolset and this target's cache
        # variables, so there's exactly one place those are declared.
        install_cmd = ["conan", "install", ".", "--output-folder", str(build_dir),
                        "--update", "--build=missing",
                        "-o", f"project={args.project}", "-s", f"build_type={build_type}"]
        configure_cmd = ["cmake", "--preset", f"{args.target}-{args.platform}",
                         "-B", str(build_dir),
                         f"-DCMAKE_TOOLCHAIN_FILE={build_dir / 'conan_toolchain.cmake'}",
                         f"-DADAS_PROJECT={args.project}"]
        build_cmd = ["cmake", "--build", str(build_dir), "--config", build_type]
        test_cmd = ["ctest", "--test-dir", str(build_dir), "-C", build_type,
                    "--output-on-failure"]

    log("Installing Conan dependencies...")
    run(install_cmd, cwd=ROOT)

    log(f"Configuring {args.target}-{args.platform} into {build_dir} (project={args.project}) ...")
    run(configure_cmd, cwd=ROOT)

    log(f"Building {args.target}-{args.platform} ...")
    run(build_cmd, cwd=ROOT)

    if args.target in TEST_TARGETS:
        log("Running tests...")
        run(test_cmd, cwd=ROOT)

    log(f"\nBuild finished for target: {args.target} (platform: {args.platform}, project: {args.project})")


if __name__ == "__main__":
    main()
