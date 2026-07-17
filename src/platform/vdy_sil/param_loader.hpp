// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VDY
/// @file
/// @brief
///   ParamLoader: loads and sections a project's YAML config file.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include <string>
#include <yaml-cpp/yaml.h>

#include "component/common/framework/vdy_params.hpp"

#if defined(_WIN32)
#if defined(VDY_SIL_EXPORTS)
#define VDY_SIL_API __declspec(dllexport)
#else
#define VDY_SIL_API __declspec(dllimport)
#endif
#else
#define VDY_SIL_API
#endif

namespace adas::vdy {

class VDY_SIL_API ParamLoader {
public:
  explicit ParamLoader(const std::string& configPath);

  VdyParams section(const std::string& functionName) const;
  VdyParams root() const;

private:
  YAML::Node root_;
};

}  // namespace adas::vdy
