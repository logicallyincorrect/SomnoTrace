/*
 * SomnoTrace - OTA flash operations on the retained internal-stack executor
 * Copyright (C) 2026 Ilya Kruchinin <https://github.com/ilyakruchinin>
 *
 * This file is part of SomnoTrace.
 *
 * SomnoTrace is free software: you can redistribute it and/or modify it under
 * the terms of the GNU General Public License as published by the Free Software
 * Foundation, either version 3 of the License, or (at your option) any later
 * version.
 *
 * SomnoTrace is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
 * A PARTICULAR PURPOSE. See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * this program. If not, see <https://www.gnu.org/licenses/>.
 *
 * ADDITIONAL TERM (GPLv3 Section 7(b)): Redistributions must preserve the
 * attribution "Based on SomnoTrace, originally created by Ilya Kruchinin
 * (https://github.com/ilyakruchinin)." See the NOTICE file for details.
 */

#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"
#include "esp_ota_ops.h"
#include "esp_partition.h"

typedef bool (*ota_flash_abort_fn_t)(void *context);

typedef struct {
    const esp_partition_t *partition;
    esp_ota_handle_t handle;
    bool begun;
} ota_flash_session_t;

/* Each operation executes synchronously on flash_executor's retained internal
 * stack. The session and buffers may reside in PSRAM. Passing NULL for the
 * partition selects the next inactive OTA partition on the executor. */
esp_err_t ota_flash_session_begin(ota_flash_session_t *session, const esp_partition_t *partition);
esp_err_t ota_flash_session_write(ota_flash_session_t *session,
                                  const void *data,
                                  size_t size,
                                  ota_flash_abort_fn_t should_abort,
                                  void *abort_context);
esp_err_t ota_flash_session_finish(ota_flash_session_t *session,
                                   ota_flash_abort_fn_t should_abort,
                                   void *abort_context);
esp_err_t ota_flash_session_read(const ota_flash_session_t *session,
                                 size_t offset,
                                 void *data,
                                 size_t size);
esp_err_t ota_flash_session_select(const ota_flash_session_t *session);
void ota_flash_session_abort(ota_flash_session_t *session);
