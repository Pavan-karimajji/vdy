from conan import ConanFile
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from pathlib import Path
import re
import yaml

# =====================================================================
# ONE conanfile.py, byte-identical in every component repo (plan.md item
# 20, docs/conanfile_commonality_plan.md). Nothing in this file is
# per-component: every real difference between components is DATA in that
# component's own conf/build.yml (the `recipe:` block and `variants:`) or
# is derived from its own CMakeLists.txt project() line. Do NOT hand-edit
# this file per component - change conf/build.yml instead. CI enforces
# `diff -q` across all copies (§8.4).
# =====================================================================


def _conf(recipe_folder):
    return yaml.safe_load((Path(recipe_folder) / "conf" / "build.yml").read_text(encoding="utf-8"))


class AdasComponent(ConanFile):
    # package_type is the one recipe attribute Conan reads before any hook
    # runs, so it can't come from set_name()/init() cleanly - it's read from
    # conf/build.yml's recipe.type at class-body import time. Verified across
    # conan inspect / conan create (cache export) / graph-info-as-dependency
    # (docs/conanfile_commonality_plan.md §7.4). conf/* is `exports` (below),
    # so the cached recipe copy can read it too.
    package_type = _conf(Path(__file__).parent)["recipe"]["type"]

    settings = "os", "arch", "compiler", "build_type"

    # Real Conan option (not an env var) so `project` participates in
    # package_id automatically - plan.md item 14 Bug #16: ADAS_PROJECT read via
    # os.environ was invisible to Conan's package identity, so base and cus1
    # produced a byte-identical package_id. "ANY" (not an enumerated list) so a
    # new project needs no conanfile.py change - conf/build.yml's variants: dict
    # stays the single source of truth (an unknown project fails naturally in
    # _build_conf() with a KeyError).
    options = {
        "project": ["ANY"],
    }

    # Superset of every component's default_options. Options for a dependency
    # not in this component's graph are simply ignored by Conan, so carrying
    # yaml-cpp/protobuf toggles everywhere is harmless and keeps the file common.
    default_options = {
        "project": "base",
        "protobuf/*:shared": False,
        "protobuf/*:with_zlib": False,
        "yaml-cpp/*:shared": False,
    }

    # Supersets of every component's file sets. Conan silently ignores export
    # patterns that match nothing, so this is safe in every component. conf/ is
    # `exports` (not exports_sources) because requirements()/build_requirements()
    # and the class-body package_type read run at graph time, before
    # exports_sources are materialized - only `exports` is available that early
    # (a real `conan create` fails with FileNotFoundError otherwise; editable
    # mode never exercises that path). CMakePresets.json is deliberately NOT
    # exported: it's build.py's hand-authored presets and would collide with the
    # ones Conan's own CMakeToolchain generates for `conan create`.
    exports = "conf/*"
    exports_sources = "CMakeLists.txt", "src/*", "cpp/*", "proto/*", "cmake/*", "projects/*"

    # ---- data helpers -----------------------------------------------------
    def _build_conf_for(self, project):
        return _conf(self.recipe_folder)["variants"][project]

    def _build_conf(self):
        return self._build_conf_for(str(self.options.project))

    def _recipe_meta(self):
        return _conf(self.recipe_folder).get("recipe", {})

    def _cmake_name(self):
        # Convention: the package name maps 1:1 to its CMake target/file name,
        # so neither has to be stored as data. adas-vdy -> AdasVdy,
        # adas-shared-config -> AdasSharedConfig.
        return "".join(part.capitalize() for part in self.name.split("-"))

    # ---- identity: name + version from CMakeLists.txt / VERSION -----------
    def set_name(self):
        content = (Path(self.recipe_folder) / "CMakeLists.txt").read_text(encoding="utf-8")
        match = re.search(r"project\(\s*([A-Za-z0-9_\-]+)", content)
        if not match:
            raise RuntimeError("Could not extract project name from CMakeLists.txt")
        self.name = match.group(1)

    def set_version(self):
        cmakelists = Path(self.recipe_folder) / "CMakeLists.txt"
        content = cmakelists.read_text(encoding="utf-8")
        match = re.search(
            rf"project\(\s*{re.escape(self.name)}\s+VERSION\s+([0-9]+\.[0-9]+\.[0-9]+)",
            content, re.IGNORECASE)
        if match:
            self.version = match.group(1)
        else:
            # Components whose project() carries no VERSION (e.g. a pure-data
            # package with LANGUAGES NONE) keep their version in a VERSION file.
            self.version = (Path(self.recipe_folder) / "VERSION").read_text(encoding="utf-8").strip()

    # ---- dependencies (read straight from conf/build.yml) -----------------
    def requirements(self):
        for ref in self._build_conf().get("requires", []):
            self.requires(ref)

    def build_requirements(self):
        for ref in self._build_conf().get("tool_requires", []):
            self.tool_requires(ref)

    def layout(self):
        # plan.md item 11, docs/sil_dependency_wiring_plan.md - editable-mode
        # consumers (e.g. sil's --local df vdy) resolve headers/libs via
        # self.cpp.source/self.cpp.build below, entirely independent of
        # package()/package_info() (which only run for a real `conan create`,
        # never exercised by editable mode). Branches on this component's own
        # layout_kind and Conan's own self.package_type.
        conf_path = Path(self.recipe_folder) / "conf" / "build.yml"
        conf = yaml.safe_load(conf_path.read_text(encoding="utf-8"))
        layout_kind = conf.get("layout_kind", "output_folder")

        if layout_kind == "cmake_layout":
            cmake_layout(self)
            self.cpp.source.includedirs = ["cpp"]
            self.cpp.build.includedirs = ["generated"]
        elif self.package_type in ("shared-library", "static-library"):
            # output_folder-kind compiled libraries (df/vdy): the real artifact
            # lives under build.py's own build-sil-<platform>/src/platform/
            # <comp>_sil/<config>/ - not a package()/install() folder, so that
            # path is named here, derived from data (component name,
            # conf/build.yml's platform), not hardcoded per component.
            comp = self.name.replace("adas-", "")
            platform = conf["variants"][str(self.options.project)]["sil"]["platforms"][0]["build"]
            build_type = str(self.settings.build_type) if self.settings.get_safe("build_type") else "Release"
            self.cpp.source.includedirs = [f"src/platform/{comp}_sil"]
            self.cpp.build.libdirs = [f"build-sil-{platform}/src/platform/{comp}_sil/{build_type}"]
            self.cpp.build.bindirs = [f"build-sil-{platform}/src/platform/{comp}_sil/{build_type}"]
        # package_type application/unknown need no override here - application
        # components are never find_package()'d by another component, and data's
        # real files sit directly in the source tree already.

    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()

        deps = CMakeDeps(self)
        deps.build_context_activated = ["protobuf"]
        deps.build_context_suffix = {"protobuf": "_BUILD"}
        deps.generate()

    # ---- build/package, defined once, no-op where package_type has nothing
    #      to compile through Conan (application: built via build.py/aggregator)
    def build(self):
        if self.package_type in ("shared-library", "static-library", "unknown"):
            cmake = CMake(self)
            enabled = self._build_conf().get("enabled_functions")
            variables = {"ENABLED_FUNCTIONS": ";".join(enabled)} if enabled else None
            cmake.configure(variables=variables)
            cmake.build()

    def package(self):
        if self.package_type in ("shared-library", "static-library", "unknown"):
            CMake(self).install()

    def package_id(self):
        # Pure-data packages (package_type unknown, e.g. shared_config) collapse
        # os/arch/compiler/build_type away - one universal package regardless of
        # profile, since the packaged content never varies by platform.
        if self.package_type == "unknown":
            self.info.clear()
            return
        # Otherwise fold every conf recipe.package_id_extra key into the hash
        # (df's enabled_functions: base 'aeb' and cus1 'aeb;bsd' become distinct
        # packages). Reads self.info.options.project, NOT self.options.project
        # ("'self.options' access in package_id() is forbidden" - hard Conan
        # error); self.info.options already mirrors the final resolved options.
        for key in self._recipe_meta().get("package_id_extra", []):
            value = self._build_conf_for(str(self.info.options.project)).get(key, [])
            setattr(self.info.options, key, ";".join(value) if isinstance(value, list) else value)

    def package_info(self):
        # Applications are never consumed by another component - nothing to
        # declare.
        if self.package_type == "application":
            return
        meta = self._recipe_meta()
        if self.package_type == "unknown":
            # Pure-data package: expose its resource dirs, no libs/includes.
            self.cpp_info.includedirs = []
            self.cpp_info.libdirs = []
            self.cpp_info.resdirs = meta.get("resdirs", ["projects"])
        else:
            self.cpp_info.libs = meta["libs"]
        name = self._cmake_name()
        self.cpp_info.set_property("cmake_target_name", f"{name}::{name}")
        self.cpp_info.set_property("cmake_file_name", name)
