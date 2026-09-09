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

#include "flash_executor.h"

#include <limits.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "esp_log.h"

static const char *TAG = "flash_executor";

/* Retained internal-RAM stack for short NVS, partition, and OTA operations.
 * Keeping it alive avoids allocating a second internal task at peak load. */
#define FLASH_EXECUTOR_STACK 8192
#define FLASH_EXECUTOR_PRIO 6 /* >= httpd worker so a submitted write runs promptly */

typedef struct {
    flash_executor_fn_t fn;
    void *arg;
    esp_err_t result;
} flash_command_t;

static QueueHandle_t s_cmd_q = NULL;          /* holds flash_command_t* */
static SemaphoreHandle_t s_submit_mtx = NULL; /* serialises submitters */
static SemaphoreHandle_t s_done = NULL;       /* writer -> submitter completion */
static SemaphoreHandle_t s_flash_lock = NULL; /* global NVS access serialisation */
static volatile uint8_t s_init_state = 0;     /* 0=not attempted, 1=ready, 2=failed */

void flash_executor_lock(void)
{
    if (s_flash_lock)
        xSemaphoreTakeRecursive(s_flash_lock, portMAX_DELAY);
}

void flash_executor_unlock(void)
{
    if (s_flash_lock)
        xSemaphoreGiveRecursive(s_flash_lock);
}

static void flash_executor_task(void *arg)
{
    (void)arg;
    UBaseType_t lowest_high_water = UINT_MAX;
    for (;;) {
        flash_command_t *cmd = NULL;
        if (xQueueReceive(s_cmd_q, &cmd, portMAX_DELAY) == pdTRUE && cmd) {
            /* Acquire the global NVS lock so that direct NVS callers (which
             * call flash_executor_lock/unlock around their own nvs_open/commit)
             * are serialized with proxy operations.  This prevents a
             * concurrent flash erase from disabling the cache while the
             * other task is mid-read from flash-mapped memory. */
            flash_executor_lock();
            cmd->result = cmd->fn ? cmd->fn(cmd->arg) : ESP_ERR_INVALID_ARG;
            flash_executor_unlock();

            UBaseType_t high_water = uxTaskGetStackHighWaterMark(NULL);
            if (high_water < lowest_high_water) {
                lowest_high_water = high_water;
                ESP_LOGI(TAG,
                         "lowest stack high-water = %u bytes",
                         (unsigned)(high_water * sizeof(StackType_t)));
            }
            if (high_water < 512) {
                ESP_LOGW(TAG,
                         "low stack watermark after flash operation: %u words",
                         (unsigned)high_water);
            }
            xSemaphoreGive(s_done);
        }
    }
}

void flash_executor_init(void)
{
    if (s_init_state != 0)
        return;       /* already initialised/failed */
    s_init_state = 2; /* fail closed until fully ready */

    s_submit_mtx = xSemaphoreCreateMutex();
    s_done = xSemaphoreCreateBinary();
    s_flash_lock = xSemaphoreCreateRecursiveMutex();
    s_cmd_q = xQueueCreate(1, sizeof(flash_command_t *));
    if (!s_submit_mtx || !s_done || !s_flash_lock || !s_cmd_q) {
        ESP_LOGE(TAG, "alloc failed (mtx=%p done=%p q=%p)", s_submit_mtx, s_done, s_cmd_q);
        s_cmd_q = NULL; /* flash_executor_run() will fail closed */
        return;
    }

    if (xTaskCreatePinnedToCore(flash_executor_task,
                                "flash_executor",
                                FLASH_EXECUTOR_STACK,
                                NULL,
                                FLASH_EXECUTOR_PRIO,
                                NULL,
                                0) != pdPASS) {
        ESP_LOGE(TAG, "task create failed; flash proxy will fail closed");
        s_cmd_q = NULL;
        return;
    }
    s_init_state = 1;
    ESP_LOGI(TAG, "flash_executor task started (internal stack=%d bytes)", FLASH_EXECUTOR_STACK);
}

esp_err_t flash_executor_run(flash_executor_fn_t fn, void *arg)
{
    if (!fn)
        return ESP_ERR_INVALID_ARG;

    /* Before initialisation is attempted, early boot callers are still on an
     * internal-RAM stack and may run inline. After an init failure, fail closed
     * rather than performing a flash operation from an unknown stack. */
    if (s_init_state == 0)
        return fn(arg);
    if (s_init_state != 1 || !s_cmd_q)
        return ESP_ERR_INVALID_STATE;

    xSemaphoreTake(s_submit_mtx, portMAX_DELAY);
    flash_command_t cmd = {.fn = fn, .arg = arg, .result = ESP_FAIL};
    flash_command_t *p = &cmd;
    xQueueSend(s_cmd_q, &p, portMAX_DELAY);
    xSemaphoreTake(s_done, portMAX_DELAY);
    esp_err_t r = cmd.result;
    xSemaphoreGive(s_submit_mtx);
    return r;
}
