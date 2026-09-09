/*
 * SomnoTrace - Centralised internal-stack flash executor
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

#include "esp_err.h"

/*
 * A task with a PSRAM-backed stack cannot itself perform SPI-flash writes: the
 * flash routine runs with the cache disabled on its own core, and accessing
 * its PSRAM stack mid-operation faults. (Other PSRAM-stack tasks are protected
 * by CONFIG_SPI_FLASH_AUTO_SUSPEND, but the task *executing* the write is not.)
 *
 * To let PSRAM-stack workers access NVS and install OTA images safely, short
 * flash operations are funnelled to this retained task with an internal-RAM
 * stack. The submitting task blocks until the operation completes.
 */

/* Callback executed on the retained internal-stack task. It may perform short,
 * synchronous NVS, partition, or OTA operations. It must copy arguments into
 * internal-stack locals before entering an operation that disables the cache;
 * the caller-owned command may live in PSRAM. Network, filesystem, and other
 * long-running work must remain on the caller task. */
typedef esp_err_t (*flash_executor_fn_t)(void *arg);

/* Create the executor task + queue. Idempotent. MUST be called before any task
 * with a PSRAM stack (e.g. the httpd worker) can invoke flash_executor_run(). */
void flash_executor_init(void);

/* Run fn(arg) on the internal-stack executor and block until it finishes,
 * returning fn's result. If the executor has not yet been initialised during
 * early boot, fn runs inline on the calling task (which at that point has an
 * internal stack). If initialisation was attempted but failed, returns
 * ESP_ERR_INVALID_STATE rather than performing an unsafe inline flash access. */
esp_err_t flash_executor_run(flash_executor_fn_t fn, void *arg);

/* Global flash/NVS access lock. ALL NVS access — both proxy
 * (flash_executor_run) and direct (nvs_open/nvs_commit from internal-stack
 * tasks) — must be serialized with OTA writes. A concurrent erase/write can
 * disable the cache while another task reads flash-mapped memory and cause an
 * MMU entry fault.
 *
 * Usage from direct NVS callers (internal-stack tasks only):
 *   flash_executor_lock();
 *   nvs_open(...);
 *   nvs_get_str(...);
 *   nvs_close(h);
 *   flash_executor_unlock();
 *
 * flash_executor_run() acquires this lock internally; callers that use the proxy
 * do NOT need to call lock/unlock themselves. Executor callbacks must never
 * call flash_executor_run() recursively or acquire this lock themselves. */
void flash_executor_lock(void);
void flash_executor_unlock(void);
