// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VDY
/// @file
/// @brief
///   VdyFunction gtest suite.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include <gtest/gtest.h>

#include "component/vdy_function.hpp"

namespace adas::vdy {
namespace {

VdyParams testParams() {
  return VdyParams(YAML::Load("VDY_MAX_AGE_VEH_SIG_S: 0.2\n"));
}

TEST(VdyFunctionTest, RunningWhenVehSigFreshAndValid) {
  VdyReqPorts reqPorts;
  reqPorts.vehSig.valid = true;
  reqPorts.vehSig.ageS = 0.05;
  VdyProPorts proPorts;

  VdyFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_EQ(fn.compState().state(), adas::df::CompState::RUNNING);
  EXPECT_EQ(fn.compState().function(), "vdy");
  EXPECT_TRUE(proPorts.compState.updated);
}

TEST(VdyFunctionTest, ErrorWhenVehSigStale) {
  VdyReqPorts reqPorts;
  reqPorts.vehSig.valid = true;
  reqPorts.vehSig.ageS = 5.0;  // older than VDY_MAX_AGE_VEH_SIG_S
  VdyProPorts proPorts;

  VdyFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_EQ(fn.compState().state(), adas::df::CompState::ERROR);
}

TEST(VdyFunctionTest, ErrorWhenVehSigNeverReceived) {
  VdyReqPorts reqPorts;
  reqPorts.vehSig.valid = false;
  VdyProPorts proPorts;

  VdyFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_EQ(fn.compState().state(), adas::df::CompState::ERROR);
}

TEST(VdyFunctionTest, CompStateIsNotInitializedBeforeFirstExec) {
  VdyReqPorts reqPorts;
  VdyProPorts proPorts;
  VdyFunction fn(reqPorts, proPorts);

  EXPECT_EQ(fn.compState().state(), adas::df::CompState::NOT_INITIALIZED);
}

TEST(VdyFunctionTest, VehDynAlwaysPublishedAsZeroPlaceholder) {
  VdyReqPorts reqPorts;
  reqPorts.vehSig.valid = true;
  reqPorts.vehSig.ageS = 0.05;
  VdyProPorts proPorts;

  VdyFunction fn(reqPorts, proPorts);
  fn.init(testParams());
  fn.exec(0.05);

  EXPECT_TRUE(proPorts.vehDyn.updated);
  EXPECT_FLOAT_EQ(proPorts.vehDyn.data.longitudinal().velocity(), 0.0f);
  EXPECT_FLOAT_EQ(proPorts.vehDyn.data.lateral().yaw_rate().yaw_rate(), 0.0f);
}

}  // namespace
}  // namespace adas::vdy
