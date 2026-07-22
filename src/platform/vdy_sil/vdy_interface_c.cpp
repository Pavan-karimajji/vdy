// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VDY
/// @file
/// @brief
///   vdy_sil.dll's C-API implementation (vdyInit/vdyExec/vdyShutdown).
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#include "vdy_interface_c.h"

#include <cstring>
#include <string>

#include "param_loader.hpp"
#include "component/vdy_function.hpp"

namespace {

template <typename T>
void updateReqPort(adas::vdy::ReqPort<T>& port, const VdyReqBuf* buf) {
  if (buf != nullptr && buf->valid != 0 &&
      port.data.ParseFromArray(buf->data, static_cast<int>(buf->len))) {
    port.ageS = buf->ageS;
    port.valid = true;
  } else {
    port.valid = false;
  }
}

bool writeProBuf(const google::protobuf::Message& msg, bool updated, VdyProBuf* buf) {
  if (buf == nullptr) {
    return true;
  }
  buf->updated = updated ? 1 : 0;
  std::string bytes;
  if (buf->data == nullptr || !msg.SerializeToString(&bytes) || bytes.size() > buf->cap) {
    buf->len = 0;
    return false;
  }
  std::memcpy(buf->data, bytes.data(), bytes.size());
  buf->len = bytes.size();
  return true;
}

struct VdyHandle {
  adas::vdy::VdyReqPorts reqPorts;
  adas::vdy::VdyProPorts proPorts;
  adas::vdy::VdyFunction function{reqPorts, proPorts};
};

}  // namespace

extern "C" {

int vdyApiVersion(void) { return 1; }

void* vdyInit(const char* configPath) {
  try {
    auto* handle = new VdyHandle();
    adas::vdy::ParamLoader loader(configPath != nullptr ? configPath : "");
    handle->function.init(loader.section("vdy"));
    return handle;
  } catch (...) {
    return nullptr;
  }
}

int vdyExec(void* handleOpaque, double dtS, const VdyReqBuf* vehSig,
            VdyProBuf* vehDyn, VdyProBuf* compState) {
  if (handleOpaque == nullptr) {
    return 0;
  }
  auto* handle = static_cast<VdyHandle*>(handleOpaque);

  try {
    updateReqPort(handle->reqPorts.vehSig, vehSig);
    handle->function.exec(dtS);

    bool ok = writeProBuf(handle->proPorts.vehDyn.data, handle->proPorts.vehDyn.updated, vehDyn);
    ok = writeProBuf(handle->proPorts.compState.data, handle->proPorts.compState.updated,
                      compState) &&
         ok;
    return ok ? 1 : 0;
  } catch (...) {
    return 0;
  }
}

void vdyShutdown(void* handleOpaque) {
  try {
    delete static_cast<VdyHandle*>(handleOpaque);
  } catch (...) {
  }
}

}  // extern "C"
