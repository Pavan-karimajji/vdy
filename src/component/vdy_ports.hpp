// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VDY
/// @file
/// @brief
///   VdyReqPorts/VdyProPorts: vdy's require/provide port structs.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

#include "component/common/framework/ports.hpp"

#include "common/veh_sig.pb.h"
#include "VehSigProvider__Outputs/veh_dyn.pb.h"
#include "common/comp_state.pb.h"

namespace adas::vdy {

// vdy's require-port: the raw vehicle-signal bus. One function, one input —
// no fan-in from multiple sources.
struct VdyReqPorts {
  ReqPort<adas::common::VehSig> vehSig;
};

// vdy's provide-ports. vehDyn is the estimated vehicle-dynamics output every
// other component (df's AebReqPorts::egoDyn, ...) already consumes.
// compState is the mandatory heartbeat every function publishes.
struct VdyProPorts {
  ProPort<adas::common::VehDyn> vehDyn;
  ProPort<adas::df::CompState>  compState;
};

}  // namespace adas::vdy
