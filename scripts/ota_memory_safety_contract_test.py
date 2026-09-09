#!/usr/bin/env python3
"""Structural contracts for bounded-RAM and race-safe OTA paths."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "main/net_provision.c").read_text(encoding="utf-8")
FLASH_SESSION = (ROOT / "main/ota_flash_session.c").read_text(encoding="utf-8")
PARTITIONS = (ROOT / "partitions.csv").read_text(encoding="utf-8")
DISPLAY_HEADER = (ROOT / "main/bsp_display.h").read_text(encoding="utf-8")
DISPLAY_SMALL = (ROOT / "main/bsp_display.c").read_text(encoding="utf-8")
DISPLAY_7B = (ROOT / "main/bsp_display_7b.c").read_text(encoding="utf-8")
POWER_SMALL = (ROOT / "main/bsp_power.c").read_text(encoding="utf-8")
NETPROV_HEADER = (ROOT / "main/net_provision.h").read_text(encoding="utf-8")
MAIN = (ROOT / "main/main.c").read_text(encoding="utf-8")
AS11 = (ROOT / "main/as11_ble.c").read_text(encoding="utf-8")
AS11_HEADER = (ROOT / "main/as11_ble.h").read_text(encoding="utf-8")


def function_body(name: str, source: str = SOURCE) -> str:
    match = re.search(
        rf"^[ \t]*[\w][\w\s*]*\b{name}\s*\([^;{{}}]*\)\s*\{{",
        source,
        re.MULTILINE,
    )
    if not match:
        raise AssertionError(f"missing function: {name}")
    depth = 1
    cursor = match.end()
    while cursor < len(source) and depth:
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    if depth:
        raise AssertionError(f"unterminated function: {name}")
    return source[match.end(): cursor - 1]


def function_span(name: str, source: str = SOURCE) -> tuple[int, int]:
    match = re.search(
        rf"^[ \t]*[\w][\w\s*]*\b{name}\s*\([^;{{}}]*\)\s*\{{",
        source,
        re.MULTILINE,
    )
    if not match:
        raise AssertionError(f"missing function: {name}")
    depth = 1
    cursor = match.end()
    while cursor < len(source) and depth:
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    if depth:
        raise AssertionError(f"unterminated function: {name}")
    return match.start(), cursor


# The binary is streamed into either 4 MiB slot; it is never staged in RAM.
assert re.search(r"app0,\s+app,\s+ota_0,\s+0x10000,\s+0x400000", PARTITIONS)
assert re.search(r"app1,\s+app,\s+ota_1,\s+0x410000,\s+0x400000", PARTITIONS)
assert re.search(r"^#define\s+OTA_MAX_SIZE\s+\(0x400000\)", SOURCE, re.MULTILINE)

# Flash work uses the retained internal-stack executor. Admission therefore
# keeps only a small runtime floor; the former 25.6/29.7 KiB per-route stack
# reservations must not return.
assert "#define OTA_INTERNAL_CAPS (MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)" in SOURCE
assert re.search(r"#define\s+OTA_MIN_INTERNAL_FREE\s+4096U", SOURCE)
assert re.search(r"#define\s+OTA_MIN_INTERNAL_LARGEST\s+1024U", SOURCE)
for removed in (
    "OTA_INTERNAL_RUNTIME_RESERVE_BYTES",
    "OTA_UPLOAD_TASK_STACK_BYTES",
    "OTA_FLASH_TASK_STACK_BYTES",
    "25600U",
    "29696U",
    "25U * 1024U",
    "29U * 1024U",
):
    assert removed not in SOURCE, f"legacy OTA admission reserve remains: {removed}"
admit = function_body("ota_heap_admit")
assert "heap_caps_get_free_size(OTA_INTERNAL_CAPS)" in function_body("ota_heap_snapshot")
assert "snapshot.free_bytes >= required_free" in admit
assert "snapshot.largest_block_bytes >= required_largest" in admit

upload = function_body("ota_upload_handler")
url = function_body("ota_url_handler")
sd_start = function_body("maintenance_ota_start_sd")
for body, mode, free_gate, block_gate, create in (
    (upload, 'netprov_lifecycle_try_claim("upload")', "OTA_UPLOAD_MIN_INTERNAL_FREE",
     "OTA_UPLOAD_MIN_INTERNAL_LARGEST", "ota_flash_session_begin("),
    (url, 'netprov_lifecycle_try_claim("url")', "OTA_URL_MIN_INTERNAL_FREE",
     "OTA_URL_MIN_INTERNAL_LARGEST", "psram_task_create("),
    (sd_start, 'netprov_lifecycle_try_claim("native-sd")', "OTA_UPLOAD_MIN_INTERNAL_FREE",
     "OTA_UPLOAD_MIN_INTERNAL_LARGEST", "psram_task_create("),
):
    assert mode in body
    assert "ota_storage_preflight()" in body
    assert "ota_heap_admit(" in body
    assert free_gate in body and block_gate in body
    assert body.index("ota_storage_preflight()") < body.index(create)
    assert body.index("ota_heap_admit(") < body.index(create)
assert "ota_send_busy(req)" in upload and "ota_send_resource_error(req" in upload
assert "ota_send_busy(req)" in url and "ota_send_resource_error(req" in url

assert 'httpd_resp_set_status(req, "409 Conflict")' in function_body("ota_send_busy")
resource_error = function_body("ota_send_resource_error")
assert 'httpd_resp_set_status(req, "503 Service Unavailable")' in resource_error
for field in ("internal_free", "internal_largest", "required_free", "required_largest"):
    assert field in resource_error

# Ordinary API and credential-save restarts reserve the same lifecycle before
# their worker is created, so URL OTA cannot claim and begin in the scheduling
# gap. Allocation and all therapy/storage deferrals release that claim.
reboot_handler = function_body("reboot_post_handler")
save_handler = function_body("save_post_handler")
generic_reboot = function_body("reboot_task")
for handler in (reboot_handler, save_handler):
    claim_pos = handler.index('netprov_lifecycle_try_claim("reboot")')
    create_pos = handler.index("psram_task_create(reboot_task", claim_pos)
    assert claim_pos < create_pos
    assert "netprov_lifecycle_release()" in handler[create_pos:]
assert "bsp_display_try_reserve_therapy_safe_restart()" in generic_reboot
assert "bsp_display_try_commit_therapy_safe_restart()" in generic_reboot
assert generic_reboot.index("bsp_display_try_reserve_therapy_safe_restart()") \
       < generic_reboot.index("sd_storage_lease_acquire(SD_LEASE_DESTRUCTIVE") \
       < generic_reboot.index("bsp_display_try_commit_therapy_safe_restart()") \
       < generic_reboot.index("sd_storage_deinit()") \
       < generic_reboot.index("esp_restart()")
assert generic_reboot.count("netprov_lifecycle_release()") >= 3
assert generic_reboot.count("bsp_display_cancel_therapy_safe_restart()") >= 2
assert "sd_storage_lease_acquire(SD_LEASE_DESTRUCTIVE, 0)" in generic_reboot

# The lifecycle claim is a public cross-module primitive. Every controlled
# restart acquires it before scheduling/entering its restart path and releases
# it whenever the operation returns without rebooting.
assert "bool netprov_lifecycle_try_claim(const char *owner);" in NETPROV_HEADER
assert "void netprov_lifecycle_release(void);" in NETPROV_HEADER
assert re.search(r"^bool netprov_lifecycle_try_claim\(", SOURCE, re.MULTILINE)
assert re.search(r"^void netprov_lifecycle_release\(", SOURCE, re.MULTILINE)
claim = function_body("netprov_lifecycle_try_claim")
assert claim.index("portENTER_CRITICAL(&s_lifecycle_claim_lock)") \
       < claim.index("if (!s_lifecycle_claimed)") \
       < claim.index("s_lifecycle_claimed = true") \
       < claim.index("portEXIT_CRITICAL(&s_lifecycle_claim_lock)")
release_claim = function_body("netprov_lifecycle_release")
assert release_claim.index("portENTER_CRITICAL(&s_lifecycle_claim_lock)") \
       < release_claim.index("s_lifecycle_claimed = false") \
       < release_claim.index("portEXIT_CRITICAL(&s_lifecycle_claim_lock)")

ui_reboot_handler = function_body("reboot_cb", DISPLAY_7B)
ui_reboot_task = function_body("reboot_task", DISPLAY_7B)
assert ui_reboot_handler.index('netprov_lifecycle_try_claim("ui-reboot")') \
       < ui_reboot_handler.index("xTaskCreate(reboot_task")
assert "netprov_lifecycle_release()" in ui_reboot_handler
assert ui_reboot_task.index("bsp_display_try_reserve_therapy_safe_restart()") \
       < ui_reboot_task.index("sd_storage_lease_acquire(SD_LEASE_DESTRUCTIVE, 0)") \
       < ui_reboot_task.index("bsp_display_try_commit_therapy_safe_restart()") \
       < ui_reboot_task.index("esp_restart()")
assert ui_reboot_task.count("netprov_lifecycle_release()") >= 3

main_reboot = function_body("controlled_restart", MAIN)
assert main_reboot.index('netprov_lifecycle_try_claim("main-reboot")') \
       < main_reboot.index("bsp_display_try_reserve_therapy_safe_restart()") \
       < main_reboot.index("sd_storage_lease_acquire(SD_LEASE_DESTRUCTIVE, 0)") \
       < main_reboot.index("bsp_display_try_commit_therapy_safe_restart()") \
       < main_reboot.index("esp_restart()")
assert main_reboot.count("netprov_lifecycle_release()") >= 3

actions = function_body("actions_handler")
format_task = function_body("format_sd_task")
format_branch = actions[actions.index('strcmp(action, "format-sd")'):]
assert format_branch.index('netprov_lifecycle_try_claim("format")') \
       < format_branch.index("psram_task_create(format_sd_task")
assert "netprov_lifecycle_release()" in format_branch
assert format_task.index("sd_storage_format()") \
       < format_task.index("bsp_display_try_reserve_therapy_safe_restart()") \
       < format_task.index("bsp_display_try_commit_therapy_safe_restart()") \
       < format_task.index("esp_restart()")
assert "sd_storage_lease_acquire(SD_LEASE_DESTRUCTIVE, 0)" in format_task
assert format_task.count("netprov_lifecycle_release()") == 1
format_success = format_task[
    format_task.index("if (ret == ESP_OK)"):
    format_task.index('ESP_LOGE(TAG, "format_sd_task: failed')
]
assert format_success.index("sd_storage_lease_release(SD_LEASE_DESTRUCTIVE)") \
       < format_success.index("uploader_reset_state()") \
       < format_success.index("for (;;)") \
       < format_success.index("bsp_display_try_reserve_therapy_safe_restart()")
assert "netprov_lifecycle_release()" not in format_success

# Census actual restart statements across all production C sources and account
# for every one inside the audited gated functions. A new raw restart cannot
# silently bypass this contract.
production_c = list((ROOT / "main").rglob("*.c")) + \
               list((ROOT / "components").rglob("*.c"))
restart_counts = {}
for path in production_c:
    text = path.read_text(encoding="utf-8")
    count = len(re.findall(r"\besp_restart\s*\(\s*\)\s*;", text))
    if count:
        restart_counts[str(path.relative_to(ROOT))] = count
assert restart_counts == {
    "main/bsp_display_7b.c": 1,
    "main/main.c": 1,
    "main/net_provision.c": 4,
}
audited_restart_bodies = (
    generic_reboot,
    ui_reboot_task,
    main_reboot,
    format_task,
    function_body("ota_wait_for_safe_reboot"),
    function_body("factory_reset_task"),
)
assert all(body.count("esp_restart()") == 1 for body in audited_restart_bodies)
assert SOURCE.count("psram_task_create(reboot_task") == 2

# EnterTherapy through the raw JSON-RPC endpoint is detected structurally and
# holds the same therapy-start claim across RPC acceptance and publication.
passthrough = function_body("ble_passthrough_handler")
assert "cJSON_Parse(body)" in passthrough
assert 'strcmp(field->valuestring, "EnterTherapy") == 0' in passthrough
assert passthrough.index('httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "invalid JSON")') \
       < passthrough.index("as11_ble_passthrough_rpc_tracked(")
assert "batched EnterTherapy is not supported" in passthrough
assert passthrough.index("bsp_display_reserve_therapy_start()") \
       < passthrough.index("as11_ble_passthrough_rpc_tracked(") \
       < passthrough.index("bsp_display_set_therapy_active(true)") \
       < passthrough.rindex("bsp_display_release_therapy_start()")
rpc_pos = passthrough.index("as11_ble_passthrough_rpc_tracked(")
unknown_publish = passthrough.index(
    "if (may_have_run && bsp_display_set_therapy_active(true))", rpc_pos
)
unknown_release = passthrough.index(
    "bsp_display_release_therapy_start()", unknown_publish
)
assert rpc_pos < unknown_publish < unknown_release

# Uploads stay on the HTTP owner and synchronously submit short operations to
# ota_flash_session. No dynamic flash task or cross-task context remains.
for removed in ("ota_flash_task", "ota_upload_context_create", "ota_ctx_t"):
    assert removed not in SOURCE, f"obsolete upload worker remains: {removed}"
for removed in (
    "xStreamBufferCreate",
    "xEventGroupCreate",
    "xEventGroupWaitBits",
    "vTaskDelete(flash_task)",
):
    assert removed not in upload, f"upload still owns cross-task state: {removed}"
assert "psram_task_create(" not in upload
assert "xTaskCreate(" not in upload
assert "heap_caps_malloc(OTA_CHUNK_SIZE, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)" in upload
assert upload.index("somnotrace_firmware_target_matches") \
       < upload.index("ota_flash_session_begin(") \
       < upload.index("ota_flash_session_write(")

before_finish = upload.index("ota_native_should_abort()", upload.index("MAINT_OTA_VERIFY"))
finish = upload.index("ota_flash_session_finish(")
after_finish = upload.index("ota_native_should_abort()", finish)
reserve = upload.index("ota_native_commit_begin()", after_finish)
select = upload.index("ota_flash_session_select(", reserve)
assert before_finish < finish < after_finish < reserve < select
assert "ota_flash_session_abort(&flash)" in upload

# Raw inactive-image operations are centralized in ota_flash_session.c. Boot
# confirmation and rollback remain in main.c and are outside this census.
raw_flash_call = re.compile(
    r"\b(?:esp_ota_(?:get_next_update_partition|begin|write|end|abort|set_boot_partition)"
    r"|esp_partition_(?:read|write|erase_range))\s*\("
)
raw_flash_sites = {}
for path in production_c:
    calls = raw_flash_call.findall(path.read_text(encoding="utf-8"))
    if calls:
        raw_flash_sites[str(path.relative_to(ROOT))] = len(calls)
assert raw_flash_sites == {"main/ota_flash_session.c": 7}

session_write = function_body("write_on_flash_task", FLASH_SESSION)
session_finish = function_body("finish_on_flash_task", FLASH_SESSION)
assert session_write.index("should_abort(abort_context)") \
       < session_write.index("esp_ota_write(")
assert session_finish.index("should_abort(abort_context)") \
       < session_finish.index("esp_ota_end(")
input_error_branch = upload[
    upload.index("if (input_error || flash_result != ESP_OK)"):
    upload.index('ESP_LOGI(TAG, "OTA: upload complete')
]
assert "input_status" in input_error_branch
assert '"{\\\"ok\\\":false,\\\"error\\\":\\\"%s\\\"}"' in input_error_branch
assert "return httpd_resp_send" in input_error_branch
assert "HTTPD_500_INTERNAL_SERVER_ERROR" in input_error_branch
assert "esp_err_to_name(flash_result)" in input_error_branch

# OTA starts at an idle boundary, and a completed update owns a deterministic
# restart lifecycle. It waits through therapy/card activity, acquires the
# destructive lease before unmounting, and retains the OTA claim while doing
# so. Failure to allocate the helper task falls back to the current owner.
preflight = function_body("ota_storage_preflight")
assert "bsp_display_is_therapy_active()" in preflight
assert "sd_storage_recording_active()" in preflight
assert "sd_storage_lease_acquire(SD_LEASE_DESTRUCTIVE, 0)" in preflight
assert "sd_storage_lease_release(SD_LEASE_DESTRUCTIVE)" in preflight
assert preflight.index("bsp_display_try_reserve_therapy_safe_restart()") \
       < preflight.index("sd_storage_lease_acquire(SD_LEASE_DESTRUCTIVE, 0)") \
       < preflight.index("sd_storage_lease_release(SD_LEASE_DESTRUCTIVE)") \
       < preflight.rindex("bsp_display_cancel_therapy_safe_restart()")

reboot_wait = function_body("ota_wait_for_safe_reboot")
assert "for (;;)" in reboot_wait
assert "timeout_ms == UINT32_MAX" in reboot_wait
assert "return false" in reboot_wait
assert "bsp_display_is_therapy_active()" in reboot_wait
assert "sd_storage_recording_active()" in reboot_wait
assert "sd_storage_lease_acquire(SD_LEASE_DESTRUCTIVE, 0)" in reboot_wait
assert reboot_wait.index("bsp_display_try_reserve_therapy_safe_restart()") \
       < reboot_wait.index("sd_storage_lease_acquire") \
       < reboot_wait.index("bsp_display_try_commit_therapy_safe_restart()") \
       < reboot_wait.index("sd_storage_deinit()") \
       < reboot_wait.index("esp_restart()")
commit_failure = reboot_wait[
    reboot_wait.index("if (!bsp_display_try_commit_therapy_safe_restart())"):
    reboot_wait.index('ESP_LOGI(TAG, "OTA reboot: storage idle')
]
assert "sd_storage_lease_release(SD_LEASE_DESTRUCTIVE)" in commit_failure
assert commit_failure.index("sd_storage_lease_release(SD_LEASE_DESTRUCTIVE)") \
       < commit_failure.index("bsp_display_cancel_therapy_safe_restart()")
assert reboot_wait.count("bsp_display_cancel_therapy_safe_restart()") >= 3
assert "netprov_lifecycle_release()" not in reboot_wait
assert "switches to an internal emergency stack before cache disable" in reboot_wait

# Therapy-start publication and the final reboot decision use one short state
# lock in either BSP.  The one-way commit is complete before the lock is
# released, and no storage or restart call is made while that lock is held.
assert "bool bsp_display_set_therapy_active(bool active);" in DISPLAY_HEADER
assert "bool bsp_display_try_reserve_therapy_safe_restart(void);" in DISPLAY_HEADER
assert "bool bsp_display_try_commit_therapy_safe_restart(void);" in DISPLAY_HEADER
assert "void bsp_display_cancel_therapy_safe_restart(void);" in DISPLAY_HEADER
assert "bool bsp_display_reserve_therapy_start(void);" in DISPLAY_HEADER
assert "void bsp_display_release_therapy_start(void);" in DISPLAY_HEADER
for display, enter, leave in (
    (DISPLAY_SMALL, "xSemaphoreTake(s_state_mutex, portMAX_DELAY)",
     "xSemaphoreGive(s_state_mutex)"),
    (DISPLAY_7B, "portENTER_CRITICAL(&s_state_lock)",
     "portEXIT_CRITICAL(&s_state_lock)"),
):
    setter = function_body("bsp_display_set_therapy_active", display)
    reserve = function_body("bsp_display_try_reserve_therapy_safe_restart", display)
    commit = function_body("bsp_display_try_commit_therapy_safe_restart", display)
    cancel = function_body("bsp_display_cancel_therapy_safe_restart", display)
    start_reserve = function_body("bsp_display_reserve_therapy_start", display)
    start_release = function_body("bsp_display_release_therapy_start", display)
    assert enter in setter and leave in setter
    assert "therapy_gate_restart_is_reserving(&s_therapy_gate)" in setter
    assert "therapy_gate_note_start_waiter(&s_therapy_gate)" in setter
    assert "therapy_gate_remove_start_waiter(&s_therapy_gate)" in setter
    assert "vTaskDelay(1)" in setter
    assert "therapy_gate_try_set_active(&s_therapy_gate, active)" in setter
    assert "return false" in setter
    assert enter in reserve and leave in reserve
    assert "therapy_gate_try_reserve_restart(&s_therapy_gate)" in reserve
    assert enter in commit and leave in commit
    assert "therapy_gate_try_commit_restart(&s_therapy_gate)" in commit
    assert commit.index("therapy_gate_try_commit_restart") < commit.index(leave)
    assert enter in cancel and leave in cancel
    assert "therapy_gate_cancel_restart(&s_therapy_gate)" in cancel
    assert enter in start_reserve and leave in start_reserve
    assert "therapy_gate_note_start_waiter(&s_therapy_gate)" in start_reserve
    assert "therapy_gate_try_reserve_start(&s_therapy_gate)" in start_reserve
    assert enter in start_release and leave in start_release
    assert "therapy_gate_release_start(&s_therapy_gate)" in start_release
    for gate_body in (reserve, commit, cancel, start_reserve, start_release):
        assert "sd_storage_" not in gate_body and "esp_restart" not in gate_body

# Locally-issued hardware commands hold a therapy-start claim across the RPC
# gap, then publish active state before releasing it. Thus OTA cannot commit
# between command acceptance and the later machine notification.
for source in (POWER_SMALL, DISPLAY_7B):
    command = function_body("start_therapy_with_lifecycle_gate", source)
    assert command.index("bsp_display_reserve_therapy_start()") \
           < command.index("as11_ble_start_therapy_tracked(&may_have_started)") \
           < command.index("bsp_display_set_therapy_active(true)") \
           < command.index("bsp_display_release_therapy_start()")
    assert "result == ESP_OK || may_have_started" in command
assert function_body("button_monitor_task", POWER_SMALL).count(
    "start_therapy_with_lifecycle_gate()"
) == 2

# The public BLE APIs require an ambiguity outcome, and all production callers
# are accounted for. Once any GATT write is accepted locally, timeouts/failures
# remain may-have-run; only a received JSON-RPC error clears that outcome.
assert "as11_ble_start_therapy(void)" not in AS11_HEADER
assert "as11_ble_passthrough_rpc(const char" not in AS11_HEADER
all_production_source = "\n".join(
    path.read_text(encoding="utf-8") for path in production_c
)
assert not re.search(r"\bas11_ble_start_therapy\s*\(", all_production_source)
assert len(re.findall(
    r"\bas11_ble_start_therapy_tracked\s*\(", all_production_source
)) == 3  # definition plus the two gated local command wrappers
assert len(re.findall(
    r"\bas11_ble_passthrough_rpc_tracked\s*\(", all_production_source
)) == 2  # definition plus the gated HTTP endpoint

send_raw = function_body("send_fig_raw", AS11)
assert send_raw.index("ble_gattc_write_flat(") \
       < send_raw.index("*may_have_reached_peer = true") \
       < send_raw.index("wait_op(5000)")
therapy_command = function_body("therapy_command", AS11)
assert therapy_command.index("send_rpc_encrypted_tracked(") \
       < therapy_command.index("*may_have_run = request_may_have_run") \
       < therapy_command.index("wait_response(10000)")
rpc_error = therapy_command[therapy_command.index(
    'cJSON *err = cJSON_GetObjectItem(resp, "error")'
):]
assert rpc_error.index("if (err)") \
       < rpc_error.index("*may_have_run = false") \
       < rpc_error.index("return ESP_FAIL")

schedule = function_body("ota_schedule_reboot")
assert "psram_task_create(ota_reboot_task" in schedule
assert "if (!task)" in schedule
reboot_task = function_body("ota_reboot_task")
assert "ota_wait_for_safe_reboot(UINT32_MAX)" in reboot_task
url_task = function_body("ota_url_task")
for success_path in (upload, url_task):
    assert "if (!ota_schedule_reboot())" in success_path
    assert "ota_wait_for_safe_reboot(OTA_REBOOT_FALLBACK_TIMEOUT_MS)" in success_path
    assert "firmware installed; restart manually" in success_path
    assert "netprov_lifecycle_release()" in success_path
    assert "psram_task_create(reboot_task" not in success_path
assert "#define OTA_REBOOT_FALLBACK_TIMEOUT_MS 5000U" in SOURCE

# A completed image is not advertised as successful until a reboot worker has
# been scheduled (or the synchronous fallback has restarted the MCU).  The
# normal deferred path deliberately retains the claim; only the explicit
# manual-restart error path releases it.
upload_success_tail = upload[upload.index('ESP_LOGI(TAG, "OTA: upload complete'):]
assert upload_success_tail.index("if (!ota_schedule_reboot())") \
       < upload_success_tail.index('httpd_resp_sendstr(req, "{\\"ok\\":true}")')
manual_restart = upload_success_tail[
    upload_success_tail.index("if (!ota_schedule_reboot())"):
    upload_success_tail.index("ota_progress_finish(true, NULL)")
]
assert manual_restart.index("firmware installed; restart manually") \
       < manual_restart.index("netprov_lifecycle_release()") \
       < manual_restart.index("503 Service Unavailable")
assert upload_success_tail.index("ota_progress_finish(true, NULL)") \
       < upload_success_tail.index('httpd_resp_sendstr(req, "{\\"ok\\":true}")')

url_success_tail = url_task[url_task.index('ESP_LOGI(TAG, "OTA URL: flash complete'):]
assert url_success_tail.index("if (!ota_schedule_reboot())") \
       < url_success_tail.index("ota_progress_finish(true, NULL)")
assert url_success_tail.index('ota_progress_finish(false, "firmware installed; restart manually")') \
       < url_success_tail.index("netprov_lifecycle_release()") \
       < url_success_tail.index("ota_progress_finish(true, NULL)")
assert "netprov_lifecycle_release()" not in schedule

# URL and SD OTA workers use reclaimable PSRAM stacks. Any failed background
# run releases the global claim and self-deletes through the matching helper.
assert "netprov_lifecycle_release()" in url_task
assert "psram_task_delete(NULL)" in url_task
assert "vTaskDelete(NULL)" not in url_task
assert "OTA_URL_TASK_STACK_BYTES" in url
assert "MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT" in url
assert "psram_task_create(" in url
sd_task = function_body("ota_sd_task")
assert "psram_task_delete(NULL)" in sd_task
assert "vTaskDelete(NULL)" not in sd_task
assert "psram_task_create(" in sd_start

# The explicit URL read loop observes cancellation before a potentially
# blocking read and submits each buffered write with a second executor-side
# cancellation callback. Redirects are bounded and performed manually so a
# stalled peer remains bounded by the five-second client timeout.
redirect_check = function_body("ota_http_status_is_redirect")
for status in (301, 302, 303, 307, 308):
    assert str(status) in redirect_check
assert ".timeout_ms = 5000" in url_task
assert ".disable_auto_redirect = true" in url_task
assert ".max_redirection_count = 8" in url_task
assert "esp_http_client_open(client, 0)" in url_task
assert "esp_http_client_fetch_headers(client)" in url_task
assert url_task.index("esp_http_client_set_redirection(client)") \
       < url_task.index("esp_http_client_close(client)",
                        url_task.index("esp_http_client_set_redirection(client)"))
url_read_loop = url_task.index("while (true)")
url_abort = url_task.index("ota_native_should_abort()", url_read_loop)
url_read = url_task.index("esp_http_client_read(", url_abort)
url_write = url_task.index("ota_flash_session_write(", url_read)
assert url_abort < url_read < url_write
assert "ota_flash_should_abort" in url_task[url_write:url_task.index(
    "ota_progress_set_transfer", url_write
)]
url_before_finish = url_task.index("ota_native_should_abort()", url_task.index("MAINT_OTA_VERIFY"))
url_finish = url_task.index("ota_flash_session_finish(")
url_after_finish = url_task.index("ota_native_should_abort()", url_finish)
url_reserve = url_task.index("ota_native_commit_begin()", url_after_finish)
url_select = url_task.index("ota_flash_session_select(", url_reserve)
assert url_before_finish < url_finish < url_after_finish < url_reserve < url_select

# SD flashing has the same cancellation/commit fences and adds recording-
# pending cancellation while it owns the upload lease.
sd_loop = sd_task.index("while (n)")
sd_abort = sd_task.index("ota_sd_flash_should_abort(NULL)", sd_loop)
sd_write = sd_task.index("ota_flash_session_write(", sd_abort)
assert sd_abort < sd_write
assert "ota_sd_flash_should_abort" in sd_task[sd_write:sd_task.index(
    "ota_progress_set_transfer", sd_write
)]
sd_before_finish = sd_task.index("ota_native_should_abort()", sd_task.index("MAINT_OTA_VERIFY"))
sd_finish = sd_task.index("ota_flash_session_finish(")
sd_after_finish = sd_task.index("ota_native_should_abort()", sd_finish)
sd_reserve = sd_task.index("ota_native_commit_begin()", sd_after_finish)
sd_select = sd_task.index("ota_flash_session_select(", sd_reserve)
assert sd_before_finish < sd_finish < sd_after_finish < sd_reserve < sd_select
assert "sd_storage_recording_pending()" in function_body("ota_sd_flash_should_abort")

# Plain HTTP is unavailable unless the build explicitly enables ESP-IDF's
# insecure OTA transport option.
assert "bool allowed_scheme = strncmp(url, \"https://\", 8) == 0" in url
assert re.search(
    r"#if\s+CONFIG_ESP_HTTPS_OTA_ALLOW_HTTP\s+"
    r"allowed_scheme\s*=.*?http://.*?#endif",
    SOURCE,
    re.DOTALL,
)
assert '"URL must start with https://"' in url

# Operators can see current 8-bit internal heap and both route thresholds.
progress = function_body("ota_progress_handler")
assert "char resp[512]" in progress
assert "ota_progress_t progress = ota_progress_snapshot()" in progress
assert "s_ota_progress" not in progress
assert "s_ota_progress" not in url_task
for helper in (
    "ota_progress_start", "ota_progress_set_error", "ota_progress_set_total",
    "ota_progress_set_transfer", "ota_progress_set_active",
    "ota_progress_finish", "ota_progress_snapshot",
    "maintenance_ota_cancel", "ota_native_stage", "ota_native_commit_begin",
    "ota_native_boot_selected", "maintenance_ota_snapshot",
):
    helper_body = function_body(helper)
    assert "portENTER_CRITICAL(&s_ota_progress_lock)" in helper_body
    assert "portEXIT_CRITICAL(&s_ota_progress_lock)" in helper_body

# Outside the locked progress helpers, only the state and lock declarations may
# name the raw shared object. This catches future unlocked reads or mutations.
progress_helpers = (
    "ota_progress_start", "ota_progress_set_error", "ota_progress_set_total",
    "ota_progress_set_transfer", "ota_progress_set_active",
    "ota_progress_finish", "ota_progress_snapshot",
    "maintenance_ota_cancel", "ota_native_stage", "ota_native_commit_begin",
    "ota_native_boot_selected", "maintenance_ota_snapshot",
)
masked_source = SOURCE
for helper in progress_helpers:
    start, end = function_span(helper)
    masked_source = masked_source[:start] + (" " * (end - start)) + masked_source[end:]
raw_progress_lines = [
    line.strip() for line in masked_source.splitlines()
    if "s_ota_progress" in line
]
assert raw_progress_lines == [
    "static ota_progress_t s_ota_progress;",
    "static portMUX_TYPE s_ota_progress_lock = portMUX_INITIALIZER_UNLOCKED;",
]
for field in (
    "internal_free", "internal_minimum", "internal_largest",
    "upload_required_free", "upload_required_largest",
    "url_required_free", "url_required_largest",
):
    assert field in progress

print("OTA memory-safety contract passed")
