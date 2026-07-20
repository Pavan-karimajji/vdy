#!/usr/bin/env python3
"""Common build orchestrator - plan.md item 10
(docs/build_conanfile_commonization_plan.md).

Physically identical across every component in this repo (df, vdy,
perception-core, sil, interfaces, shared_config) - the only thing that
differs between components is their own conf/build.yml. No component name
or kind may ever become a code branch here; a real behavioral difference
belongs in conf/build.yml as package_kind/layout_kind/package_id_extra, or
as a component's own real target keys under variants.<project> (§2.1a),
not in this file. Propagating a future fix means re-copying this file into
every component's scripts/ by hand - an accepted cost
(docs/build_conanfile_commonization_plan.md, "Core philosophy").

Target discovery (revised 2026-07-20, §0.3/§2.1a/§7a): there is no
targets: metadata field. Every real target is its own key directly under
variants.<project>, each carrying its own platforms: list (reused via a
YAML anchor/alias where identical) - the same shape a proven external
reference (mf_trjpla.yaml) uses for its own production/testing/
documentation build kinds. target_blocks() below discovers valid targets
straight from those keys - nothing to keep in sync by hand.

Usage: python build.py <project> <part> <platform> [clean]
       python build.py config
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent  # modules/<name>/


def run(cmd, cwd):
    print(" ".join(str(c) for c in cmd))
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        sys.exit(result.returncode)


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


def target_blocks(project_conf):
    """Every key under variants.<project> that is a mapping containing a
    platforms: list is a real, declared target (§2.1a) - no separate
    targets: field to keep in sync; the YAML's own keys are the list."""
    return {
        key: value["platforms"]
        for key, value in (project_conf or {}).items()
        if isinstance(value, dict) and "platforms" in value
    }


def validate_data_component():
    projects_dir = ROOT / "projects"
    if not projects_dir.is_dir():
        sys.exit("ERROR: projects/ directory missing")
    found = list(projects_dir.glob("*/vehicle/ego_params.yaml"))
    for f in found:
        yaml.safe_load(f.read_text(encoding="utf-8"))  # raises on malformed YAML
    print(f"OK: {len(found)} project config file(s) validated under {projects_dir}")


def print_config(conf):
    """python build.py config - lists every real <project> <part> <platform>
    command this component accepts, read straight off conf/build.yml's own
    target keys (target_blocks(), §2.1a), with zero requires:/tool_requires:
    dependency-chain expansion (that's Conan's job at install time, not this
    listing's - docs/build_conanfile_commonization_plan.md §4.3)."""
    package_kind = conf.get("package_kind", "library")
    variants = conf.get("variants", {}) or {}

    if package_kind == "data":
        for project in variants:
            print(f"python build.py {project} <part> <platform>  (validate-only - part/platform ignored)")
        return

    for project, project_conf in variants.items():
        for target, platforms in target_blocks(project_conf).items():
            for platform_entry in platforms:
                print(f"python build.py {project} {target} {platform_entry['build']}")


def main():
    if sys.argv[1:] == ["config"]:
        print_config(load_conf())
        return

    p = argparse.ArgumentParser()
    p.add_argument("project")
    p.add_argument("part")
    p.add_argument("platform")
    p.add_argument("clean", nargs="?", default="")
    args = p.parse_args()

    conf = load_conf()
    package_kind = conf.get("package_kind", "library")
    layout_kind = conf.get("layout_kind", "output_folder")

    if package_kind == "data":
        validate_data_component()
        return

    project_conf = (conf.get("variants") or {}).get(args.project, {})
    blocks = target_blocks(project_conf)
    if args.part not in blocks:
        sys.exit(f"ERROR: unknown target '{args.part}' - valid: {sorted(blocks)}")

    check_conan_installed()
    warn_if_stale_profile()

    build_type = "Debug" if args.platform.endswith("_debug") else "Release"

    if layout_kind == "cmake_layout":
        build_dir = ROOT / "build"
        if args.clean == "clean":
            rmtree_if_exists(build_dir)
            (ROOT / "CMakeUserPresets.json").unlink(missing_ok=True)
        install_cmd = ["conan", "install", ".", "--update", "--build=missing",
                        "-s", f"build_type={build_type}"]
        preset = "conan-default"
        build_preset = "conan-release"
    else:  # output_folder
        build_dir = ROOT / f"build-{args.part}-{args.platform}"
        if args.clean == "clean":
            rmtree_if_exists(build_dir)
        install_cmd = ["conan", "install", ".", "--output-folder", str(build_dir),
                        "--update", "--build=missing",
                        "-o", f"project={args.project}", "-s", f"build_type={build_type}"]
        preset = f"{args.part}-{args.platform}"
        build_preset = preset

    print("Installing Conan dependencies...")
    run(install_cmd, cwd=ROOT)

    print(f"Configuring preset {preset} (project={args.project}) ...")
    run(["cmake", "--preset", preset, f"-DADAS_PROJECT={args.project}"], cwd=ROOT)

    print(f"Building preset {build_preset} ...")
    run(["cmake", "--build", "--preset", build_preset], cwd=ROOT)

    if args.part == "gtest":
        print("Running tests...")
        run(["ctest", "--preset", build_preset], cwd=ROOT)

    print(f"\nBuild finished for target: {args.part} (platform: {args.platform}, project: {args.project})")


if __name__ == "__main__":
    main()
