#pragma once

#include "esp_err.h"

/* Prepare board-level IO arbitration before the storage service mounts SD. */
esp_err_t board_storage_prepare(void);
