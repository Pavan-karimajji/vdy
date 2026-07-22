// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VDY
/// @file
/// @brief
///   ParamLoader gtest suite.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include <gtest/gtest.h>

#include "param_loader.hpp"

namespace adas::vdy {
namespace {

constexpr auto kFunctionParamsFixture = ADAS_VDY_TEST_FIXTURE_DIR "/function_params_test.yaml";
constexpr auto kEgoParamsFixture = ADAS_VDY_TEST_FIXTURE_DIR "/ego_params_test.yaml";
constexpr auto kRealBaseEgoParams = ADAS_VDY_SHARED_CONFIG_DIR "/base/vehicle/ego_params.yaml";

TEST(ParamLoaderTest, SectionReadsExistingKeyFromNamedSection) {
  ParamLoader loader(kFunctionParamsFixture);
  VdyParams vdy = loader.section("vdy");
  EXPECT_DOUBLE_EQ(vdy.get<double>("VDY_MAX_AGE_VEH_SIG_S", -1.0), 0.2);
}

TEST(ParamLoaderTest, RootReadsFlatTopLevelKey) {
  ParamLoader loader(kEgoParamsFixture);
  EXPECT_DOUBLE_EQ(loader.root().get<double>("EGO_WHEELBASE_M", -1.0), 2.7);
}

TEST(ParamLoaderTest, MissingFileFallsBackToCallerDefaultEverywhere) {
  ParamLoader loader("does/not/exist.yaml");
  EXPECT_DOUBLE_EQ(loader.section("vdy").get<double>("VDY_MAX_AGE_VEH_SIG_S", 9.0), 9.0);
  EXPECT_DOUBLE_EQ(loader.root().get<double>("EGO_WHEELBASE_M", 9.0), 9.0);
}

// Proves the shared_config-relocated ego_params.yaml actually resolves
// end-to-end through the Conan-installed package path, not just a test
// fixture copy.
TEST(ParamLoaderTest, RealBaseEgoParamsFileReadsExpectedWheelbase) {
  ParamLoader loader(kRealBaseEgoParams);
  EXPECT_DOUBLE_EQ(loader.root().get<double>("EGO_WHEELBASE_M", -1.0), 2.7);
}

}  // namespace
}  // namespace adas::vdy
