#!/usr/bin/env python3
"""Structural contracts preventing stale paired.json resurrection."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
TOP = (ROOT / "main/oximeter.c").read_text(encoding="utf-8")
OXYII = (ROOT / "main/oximeter_oxyii.c").read_text(encoding="utf-8")
LEGACY = (ROOT / "main/oximeter_legacy.c").read_text(encoding="utf-8")
INTERNAL = (ROOT / "main/oximeter_internal.h").read_text(encoding="utf-8")
NETPROV = (ROOT / "main/net_provision.c").read_text(encoding="utf-8")


def function_body(name: str, source: str) -> str:
    match = re.search(
        rf"^[\w][\w\s*]*\b{name}\s*\([^;{{}}]*\)\s*\{{",
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


def require(source: str, pattern: str, description: str) -> re.Match[str]:
    match = re.search(pattern, source, re.MULTILINE)
    if not match:
        raise AssertionError(f"missing contract: {description}")
    return match


def position(source: str, pattern: str, description: str) -> int:
    return require(source, pattern, description).start()


for source, driver in (
    (OXYII, "OX_DRIVER_OXYII"),
    (LEGACY, "OX_DRIVER_LEGACY"),
):
    save = function_body("do_save_nvs", source)
    driver_write = rf'nvs_set_u8\s*\(\s*h\s*,\s*"driver"\s*,\s*\(uint8_t\)\s*{driver}\s*\)'
    forgotten_clear = r'nvs_set_u8\s*\(\s*h\s*,\s*"forgotten"\s*,\s*0\s*\)'
    commit = r'nvs_commit\s*\(\s*h\s*\)'
    assert position(save, driver_write, "save driver") \
           < position(save, forgotten_clear, "clear forgotten tombstone") \
           < position(save, commit, "commit pairing record")
    require(
        save,
        r'if\s*\(\s*e\s*==\s*ESP_OK\s*\)\s*e\s*=\s*'
        + forgotten_clear
        + r'\s*;',
        "clear forgotten tombstone only after successful pairing writes",
    )

    pair = function_body("pair_task", source)
    persist = pair.index("nvs_writer_run(do_save_nvs, &nvs_arg)")
    persist_guard = pair.index("if (persisted != ESP_OK)", persist)
    sd_mirror = pair.index("ox_store_save_paired(", persist_guard)
    ram_publish = pair.index("s_paired = true", sd_mirror)
    assert persist < persist_guard < sd_mirror < ram_publish
    failure = pair[persist_guard:sd_mirror]
    assert "set_error(" in failure
    assert "do_disconnect()" in failure
    assert "psram_task_delete(NULL)" in failure
    assert "return;" in failure

    erase = function_body("do_erase_nvs", source)
    assert 'nvs_erase_key(h, "forgotten")' not in erase
    erase_driver = r'erase_nvs_key_if_present\s*\(\s*h\s*,\s*"driver"\s*\)'
    forgotten_set = r'nvs_set_u8\s*\(\s*h\s*,\s*"forgotten"\s*,\s*1\s*\)'
    assert position(erase, erase_driver, "erase driver") \
           < position(erase, forgotten_set, "set forgotten tombstone") \
           < position(erase, commit, "commit forgotten tombstone")
    require(
        erase,
        r'if\s*\(\s*e\s*==\s*ESP_OK\s*\)\s*e\s*=\s*'
        + forgotten_set
        + r'\s*;',
        "set forgotten tombstone only after successful erases",
    )
    require(
        erase,
        r'if\s*\(\s*e\s*==\s*ESP_OK\s*\)\s*e\s*=\s*nvs_commit\s*\(\s*h\s*\)\s*;',
        "commit forgotten tombstone only after successful writes",
    )

    erase_helper = function_body("erase_nvs_key_if_present", source)
    assert "nvs_erase_key(h, key)" in erase_helper
    assert "e == ESP_ERR_NVS_NOT_FOUND ? ESP_OK : e" in erase_helper
    for key in (
        "firmware",
        "name_prefix",
        "ble_name",
        "last_addr",
        "driver",
        "probe_mode",
    ):
        require(
            erase,
            rf'if\s*\(\s*e\s*==\s*ESP_OK\s*\)\s*e\s*=\s*'
            rf'erase_nvs_key_if_present\s*\(\s*h\s*,\s*"{key}"\s*\)\s*;',
            f"erase {key} only after prior erases succeed",
        )

    load = function_body("load_paired_from_nvs", source)
    tombstone_read = load.index('nvs_get_u8(h, "forgotten", &forgotten_value)')
    sd_fallback = load.index("ox_store_load_paired(")
    assert tombstone_read < sd_fallback
    assert "if (!s_paired && !forgotten)" in load[:sd_fallback]
    # Missing keys remain backward-compatible: only an explicitly persisted 1
    # suppresses the paired.json fallback.
    assert re.search(r'== ESP_OK\s*&&\s*forgotten_value == 1', load)
    assert "nvs_writer_unlock(); return;" not in load[:sd_fallback]

    forget_name = "oxyii_forget" if driver == "OX_DRIVER_OXYII" else "legacy_forget"
    forget = function_body(forget_name, source)
    persist = forget.index("nvs_writer_run(do_erase_nvs, NULL)")
    persist_guard = forget.index("if (persisted != ESP_OK)", persist)
    sd_mirror = forget.index("ox_store_delete_paired()", persist_guard)
    ram_clear = forget.index("s_paired = false", sd_mirror)
    assert persist < persist_guard < sd_mirror < ram_clear
    failure = forget[persist_guard:sd_mirror]
    assert "set_error(" in failure
    assert "return persisted;" in failure
    assert "return ESP_OK;" in forget[ram_clear:]


selection = function_body("load_driver_type", TOP)
assert selection.index('nvs_get_u8(h, "forgotten", &forgotten_value)') \
       < selection.index("ox_store_load_paired(")
assert "if (!forgotten && s_driver_type == OX_DRIVER_OXYII)" in selection
assert 'forgotten_value == 1' in selection

assert "esp_err_t (*forget)(void);" in INTERNAL
dispatcher = function_body("oximeter_forget", TOP)
assert "return s_active->forget();" in dispatcher
forget_http = function_body("ox_forget_handler", NETPROV)
assert forget_http.index("esp_err_t e = oximeter_forget()") \
       < forget_http.index("if (e != ESP_OK)") \
       < forget_http.index('httpd_resp_sendstr(req, "{\\"ok\\":true}")')

print("Oximetry Forget tombstone contract passed")
