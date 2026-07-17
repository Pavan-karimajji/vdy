// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VDY
/// @file
/// @brief
///   VdyFunction: staleness/validity gating + neutral VehDyn publication.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include "component/common/framework/i_vdy_function.hpp"
#include "component/vdy_ports.hpp"

namespace adas::vdy {

// vdy skeleton: input-validity/staleness checks + compState update + a
// neutral (all-zero) VehDyn every cycle. No real estimation math yet
// (yaw-rate/velocity/side-slip filtering, wheel-speed fusion, offset
// calibration) — that's a later, separate increment.
class VdyFunction final : public IVdyFunction {
public:
  VdyFunction(const VdyReqPorts& reqPorts, VdyProPorts& proPorts);

  void init(const VdyParams& params) override;
  void exec(double dtS) override;
  const adas::df::CompState& compState() const override;

private:
  const VdyReqPorts& reqPorts_;
  VdyProPorts&       proPorts_;

  double maxAgeVehSigS_ = 0.2;  // overwritten by init(); safe fallback
};

}  // namespace adas::vdy
