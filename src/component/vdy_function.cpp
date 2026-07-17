// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VDY
/// @file
/// @brief
///   VdyFunction implementation.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include "component/vdy_function.hpp"

namespace adas::vdy {

VdyFunction::VdyFunction(const VdyReqPorts& reqPorts, VdyProPorts& proPorts)
    : reqPorts_(reqPorts), proPorts_(proPorts) {}

void VdyFunction::init(const VdyParams& params) {
  maxAgeVehSigS_ = params.get<double>("VDY_MAX_AGE_VEH_SIG_S", maxAgeVehSigS_);
}

void VdyFunction::exec(double dtS) {
  (void)dtS;  // skeleton: no filtering/integration reads dt yet

  const bool vehSigFresh =
      reqPorts_.vehSig.valid && reqPorts_.vehSig.ageS <= maxAgeVehSigS_;

  adas::df::CompState state;
  state.set_function("vdy");
  state.set_state(vehSigFresh ? adas::df::CompState::RUNNING
                              : adas::df::CompState::ERROR);
  proPorts_.compState.data = state;
  proPorts_.compState.updated = true;

  // Skeleton: always publish a default-constructed (all-zero) VehDyn —
  // placeholder, not a real estimate. A later increment fills this in with
  // real yaw-rate/velocity/side-slip estimation over reqPorts_.vehSig.
  proPorts_.vehDyn.data = adas::common::VehDyn();
  proPorts_.vehDyn.updated = true;
}

const adas::df::CompState& VdyFunction::compState() const {
  return proPorts_.compState.data;
}

}  // namespace adas::vdy
