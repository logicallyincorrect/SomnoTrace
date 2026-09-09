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

#include "ota_flash_session.h"

#include "flash_executor.h"

typedef struct {
    const esp_partition_t *partition;
    esp_ota_handle_t handle;
} begin_command_t;

static esp_err_t begin_on_flash_task(void *arg)
{
    begin_command_t *command = arg;
    const esp_partition_t *partition = command->partition;
    if (!partition)
        partition = esp_ota_get_next_update_partition(NULL);
    if (!partition)
        return ESP_ERR_NOT_FOUND;
    esp_ota_handle_t handle = 0;
    esp_err_t result = esp_ota_begin(partition, OTA_WITH_SEQUENTIAL_WRITES, &handle);
    command->partition = partition;
    command->handle = handle;
    return result;
}

esp_err_t ota_flash_session_begin(ota_flash_session_t *session, const esp_partition_t *partition)
{
    if (!session || session->begun)
        return ESP_ERR_INVALID_ARG;
    begin_command_t command = {.partition = partition};
    esp_err_t result = flash_executor_run(begin_on_flash_task, &command);
    if (result == ESP_OK) {
        session->partition = command.partition;
        session->handle = command.handle;
        session->begun = true;
    }
    return result;
}

typedef struct {
    esp_ota_handle_t handle;
    const void *data;
    size_t size;
    ota_flash_abort_fn_t should_abort;
    void *abort_context;
} write_command_t;

static esp_err_t write_on_flash_task(void *arg)
{
    write_command_t *command = arg;
    esp_ota_handle_t handle = command->handle;
    const void *data = command->data;
    size_t size = command->size;
    ota_flash_abort_fn_t should_abort = command->should_abort;
    void *abort_context = command->abort_context;
    if (should_abort && should_abort(abort_context))
        return ESP_ERR_INVALID_STATE;
    return esp_ota_write(handle, data, size);
}

esp_err_t ota_flash_session_write(ota_flash_session_t *session,
                                  const void *data,
                                  size_t size,
                                  ota_flash_abort_fn_t should_abort,
                                  void *abort_context)
{
    if (!session || !session->begun || !data || size == 0)
        return ESP_ERR_INVALID_ARG;
    write_command_t command = {.handle = session->handle,
                               .data = data,
                               .size = size,
                               .should_abort = should_abort,
                               .abort_context = abort_context};
    return flash_executor_run(write_on_flash_task, &command);
}

typedef struct {
    esp_ota_handle_t handle;
    ota_flash_abort_fn_t should_abort;
    void *abort_context;
    bool aborted;
} finish_command_t;

static esp_err_t finish_on_flash_task(void *arg)
{
    finish_command_t *command = arg;
    esp_ota_handle_t handle = command->handle;
    ota_flash_abort_fn_t should_abort = command->should_abort;
    void *abort_context = command->abort_context;
    if (should_abort && should_abort(abort_context)) {
        command->aborted = true;
        return ESP_ERR_INVALID_STATE;
    }
    return esp_ota_end(handle);
}

esp_err_t ota_flash_session_finish(ota_flash_session_t *session,
                                   ota_flash_abort_fn_t should_abort,
                                   void *abort_context)
{
    if (!session || !session->begun)
        return ESP_ERR_INVALID_STATE;
    finish_command_t command = {
        .handle = session->handle, .should_abort = should_abort, .abort_context = abort_context};
    esp_err_t result = flash_executor_run(finish_on_flash_task, &command);
    /* esp_ota_end consumes the handle even when validation fails. A cancelled
     * callback returns before esp_ota_end, so the session remains abortable. */
    if (!command.aborted)
        session->begun = false;
    return result;
}

typedef struct {
    const esp_partition_t *partition;
    size_t offset;
    void *data;
    size_t size;
} read_command_t;

static esp_err_t read_on_flash_task(void *arg)
{
    read_command_t *command = arg;
    const esp_partition_t *partition = command->partition;
    size_t offset = command->offset;
    void *data = command->data;
    size_t size = command->size;
    return esp_partition_read(partition, offset, data, size);
}

esp_err_t ota_flash_session_read(const ota_flash_session_t *session,
                                 size_t offset,
                                 void *data,
                                 size_t size)
{
    if (!session || !session->partition || !data || size == 0)
        return ESP_ERR_INVALID_ARG;
    read_command_t command = {
        .partition = session->partition, .offset = offset, .data = data, .size = size};
    return flash_executor_run(read_on_flash_task, &command);
}

static esp_err_t select_on_flash_task(void *arg)
{
    const ota_flash_session_t *session = arg;
    const esp_partition_t *partition = session->partition;
    return esp_ota_set_boot_partition(partition);
}

esp_err_t ota_flash_session_select(const ota_flash_session_t *session)
{
    if (!session || !session->partition || session->begun)
        return ESP_ERR_INVALID_STATE;
    return flash_executor_run(select_on_flash_task, (void *)session);
}

static esp_err_t abort_on_flash_task(void *arg)
{
    esp_ota_handle_t handle = *(const esp_ota_handle_t *)arg;
    return esp_ota_abort(handle);
}

void ota_flash_session_abort(ota_flash_session_t *session)
{
    if (!session || !session->begun)
        return;
    esp_ota_handle_t handle = session->handle;
    (void)flash_executor_run(abort_on_flash_task, &handle);
    session->begun = false;
}
