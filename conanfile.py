from conan import ConanFile
from conan.tools.cmake import CMakeDeps, CMakeToolchain
from pathlib import Path
import os
import re
import yaml


class VdyConan(ConanFile):
    name = "adas-vdy"
    package_type = "application"

    settings = "os", "arch", "compiler", "build_type"

    default_options = {
        "protobuf/*:shared": False,
        "protobuf/*:with_zlib": False,
        "yaml-cpp/*:shared": False,
    }

    def _build_conf(self):
        conf_path = Path(self.recipe_folder) / "conf" / "build.yml"
        conf = yaml.safe_load(conf_path.read_text(encoding="utf-8"))
        project = os.environ.get("ADAS_PROJECT", "base")
        return conf["variants"][project]

    def requirements(self):
        for ref in self._build_conf().get("requires", []):
            self.requires(ref)

    def build_requirements(self):
        for ref in self._build_conf().get("tool_requires", []):
            self.tool_requires(ref)

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
