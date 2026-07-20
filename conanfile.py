from conan import ConanFile
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from pathlib import Path
import re
import yaml


class VdyConan(ConanFile):
    name = "adas-vdy"
    # The real deliverable is vdy_sil.dll (+ import lib + vdy_interface_c.h),
    # not a standalone executable - see plan.md item 14.
    package_type = "shared-library"

    settings = "os", "arch", "compiler", "build_type"

    # A real Conan option (not an env var) so it participates in
    # package_id automatically - plan.md item 14 Bug #16: ADAS_PROJECT
    # used to be read via plain os.environ.get() inside requirements(),
    # invisible to Conan's package identity, so a base build and a cus1
    # build produced the byte-identical package_id. "ANY" (not an
    # enumerated list) so a new project needs no conanfile.py change -
    # conf/build.yml's own variants: dict stays the single source of
    # truth (an unknown project still fails naturally in _build_conf()
    # below with a KeyError). No enabled_functions option here, unlike
    # df's conanfile.py - vdy's CMakeLists.txt has no such mechanism to
    # wire it to.
    options = {
        "project": ["ANY"],
    }

    default_options = {
        "project": "base",
        "protobuf/*:shared": False,
        "protobuf/*:with_zlib": False,
        "yaml-cpp/*:shared": False,
    }

    # Needed so a real `conan create` (run from the Conan cache's exported
    # copy, not this checkout) has access to the same files build.bat's
    # direct cmake invocation already sees. conf/ is `exports` (not
    # exports_sources) because requirements()/build_requirements() below
    # read conf/build.yml, and those methods run before exports_sources
    # are materialized - only `exports` is available that early.
    # CMakePresets.json is deliberately NOT exported: it's build.bat's own
    # hand-authored presets (used for its --output-folder-driven local dev
    # flow), and would collide with the CMakePresets.json Conan's own
    # CMakeToolchain generates for `conan create`'s internal build - that
    # one doesn't need ours, it uses its own auto-generated preset.
    exports = "conf/*"
    exports_sources = "CMakeLists.txt", "src/*"

    def _build_conf(self):
        conf_path = Path(self.recipe_folder) / "conf" / "build.yml"
        conf = yaml.safe_load(conf_path.read_text(encoding="utf-8"))
        return conf["variants"][str(self.options.project)]

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
        # package()/package_info() (which only run for a real `conan
        # create`, never exercised by editable mode). Same conditional
        # template copied into every component's conanfile.py (item 10's
        # own philosophy) - branches on this file's own layout_kind and
        # Conan's own self.package_type (package_kind was removed from
        # conf/build.yml entirely, docs/build_regression_tests.md §5 -
        # library/application was never read differently anywhere except
        # here, and self.package_type already carries that same
        # distinction natively).
        conf_path = Path(self.recipe_folder) / "conf" / "build.yml"
        conf = yaml.safe_load(conf_path.read_text(encoding="utf-8"))
        layout_kind = conf.get("layout_kind", "output_folder")

        if layout_kind == "cmake_layout":
            cmake_layout(self)
            self.cpp.source.includedirs = ["cpp"]
            self.cpp.build.includedirs = ["generated"]
        elif self.package_type in ("shared-library", "static-library"):
            # output_folder-kind compiled libraries (df/vdy): the real
            # artifact lives under build.py's own build-sil-<platform>/
            # src/platform/<comp>_sil/<config>/ - not a package()/install()
            # folder, so that path has to be named here, derived from data
            # (component name, conf/build.yml's own platform), not hardcoded
            # per component.
            comp = self.name.replace("adas-", "")
            platform = conf["variants"][str(self.options.project)]["sil"]["platforms"][0]["build"]
            build_type = str(self.settings.build_type) if self.settings.get_safe("build_type") else "Release"
            self.cpp.source.includedirs = [f"src/platform/{comp}_sil"]
            self.cpp.build.libdirs = [f"build-sil-{platform}/src/platform/{comp}_sil/{build_type}"]
            self.cpp.build.bindirs = [f"build-sil-{platform}/src/platform/{comp}_sil/{build_type}"]
        # package_type application/unknown need no override here - application
        # components are never find_package()'d by another component, and
        # data's real files sit directly in the source tree already.

    def set_version(self):
        cmakelists = Path(self.recipe_folder) / "CMakeLists.txt"
        content = cmakelists.read_text(encoding="utf-8")
        match = re.search(r"project\(\s*adas-vdy\s+VERSION\s+([0-9]+\.[0-9]+\.[0-9]+)", content, re.IGNORECASE)
        if not match:
            raise RuntimeError("Could not extract VERSION from CMakeLists.txt")
        self.version = match.group(1)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()

        deps = CMakeDeps(self)
        deps.build_context_activated = ["protobuf"]
        deps.build_context_suffix = {"protobuf": "_BUILD"}
        deps.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()

    def package_info(self):
        self.cpp_info.libs = ["vdy_sil"]
        self.cpp_info.set_property("cmake_target_name", "AdasVdy::AdasVdy")
        self.cpp_info.set_property("cmake_file_name", "AdasVdy")
