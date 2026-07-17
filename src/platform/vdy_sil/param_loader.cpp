// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VDY
/// @file
/// @brief
///   ParamLoader implementation: loads a project's YAML config file.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include "param_loader.hpp"

namespace adas::vdy {

ParamLoader::ParamLoader(const std::string& configPath) {
  try {
    root_ = YAML::LoadFile(configPath);
  } catch (const YAML::Exception&) {
    root_ = YAML::Node();
  }
}

VdyParams ParamLoader::section(const std::string& functionName) const {
  if (root_ && root_[functionName]) {
    return VdyParams(root_[functionName]);
  }
  return VdyParams();
}

VdyParams ParamLoader::root() const {
  return VdyParams(root_);
}

}  // namespace adas::vdy
