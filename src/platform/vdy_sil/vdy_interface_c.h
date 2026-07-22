// Copyright (c) LT EPS. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: VDY
/// @file
/// @brief
///   vdy_sil.dll's host-agnostic C-API declaration.
/// @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

#ifndef ADAS_VDY_INTERFACE_C_H_
#define ADAS_VDY_INTERFACE_C_H_

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
#if defined(VDY_SIL_EXPORTS)
#define VDY_API __declspec(dllexport)
#else
#define VDY_API __declspec(dllimport)
#endif
#else
#define VDY_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
  const uint8_t* data;
  size_t len;
  double ageS;
  int valid; /* 0/1 */
} VdyReqBuf;

typedef struct {
  uint8_t* data;
  size_t cap;
  size_t len;
  int updated; /* 0/1 */
} VdyProBuf;

VDY_API int vdyApiVersion(void);

/* configPath: path to a YAML file shaped like src/project/base/default.yaml
   (vdy's own future per-function calibration — none exists yet, an empty/
   missing file is fine, ParamLoader degrades to defaults). Returns NULL on
   error. */
VDY_API void* vdyInit(const char* configPath);

/* One cycle. vehSig: serialized VehSig (NULL if not received this tick).
   vehDyn/compState: caller-allocated output buffers (NULL if not wanted).
   Returns 1 on success, 0 on failure. */
VDY_API int vdyExec(void* handle, double dtS, const VdyReqBuf* vehSig,
                     VdyProBuf* vehDyn, VdyProBuf* compState);

VDY_API void vdyShutdown(void* handle);

#ifdef __cplusplus
}
#endif

#endif /* ADAS_VDY_INTERFACE_C_H_ */
