// Copyright (c) L&T EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VDY
/// @file
/// @brief
///   ReqPort/ProPort templates: generic require/provide port wrappers.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#pragma once

namespace adas::vdy {

// Require-port: latest value received for one input, plus how the receiving
// function should judge it — age since receipt and whether it's usable at
// all. Same shape as adas::df::ReqPort — duplicated, not shared, because
// components depend only on interfaces (CLAUDE.md), never on another
// component's internals, and this type isn't part of any interfaces contract.
template <typename T>
struct ReqPort {
  T data{};
  double ageS = 0.0;
  bool valid = false;
};

// Provide-port: one function-level output plus whether this tick produced a
// new value worth publishing.
template <typename T>
struct ProPort {
  T data{};
  bool updated = false;
};

}  // namespace adas::vdy
