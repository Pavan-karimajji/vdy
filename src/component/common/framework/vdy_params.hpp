// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VDY
/// @file
/// @brief
///   Thin wrapper around one function's YAML config section.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include <string>
#include <yaml-cpp/yaml.h>

namespace adas::vdy {

// Thin wrapper around one function's YAML config section. Confines
// yaml-cpp to this one header, same reasoning as adas::df::DfParams.
class VdyParams {
public:
  VdyParams() = default;
  explicit VdyParams(YAML::Node section) : section_(std::move(section)) {}

  template <typename T>
  T get(const std::string& key, const T& defaultValue) const {
    if (!section_ || !section_[key]) {
      return defaultValue;
    }
    return section_[key].as<T>();
  }

private:
  YAML::Node section_;
};

}  // namespace adas::vdy
