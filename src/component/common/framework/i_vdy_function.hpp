// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VDY
/// @file
/// @brief
///   IVdyFunction: lifecycle contract vdy's one function implements.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include "common/comp_state.pb.h"
#include "component/common/framework/vdy_params.hpp"

namespace adas::vdy {

// Lifecycle contract vdy's one function implements — same three calls as
// adas::df::IDfFunction (init/exec/compState), no registration/runner
// concept (vdy never has more than one function).
class IVdyFunction {
public:
  virtual ~IVdyFunction() = default;

  virtual void init(const VdyParams& params) = 0;
  virtual void exec(double dtS) = 0;
  virtual const adas::df::CompState& compState() const = 0;
};

}  // namespace adas::vdy
