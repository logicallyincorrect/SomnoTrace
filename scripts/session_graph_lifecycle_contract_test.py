#!/usr/bin/env python3
"""Check session-file ownership across storage, worker, and HTTP lifecycles."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
GRAPH = (ROOT / "main/session_graph.c").read_text()
HEADER = (ROOT / "main/session_graph.h").read_text()
NET = (ROOT / "main/net_provision.c").read_text()


def function(source: str, name: str) -> str:
    match = re.search(
        rf"^(?:static\s+)?[\w *]+\b{name}\([^;{{]*\)\s*\{{",
        source,
        re.MULTILINE,
    )
    assert match, f"missing {name}"
    offset = match.end()
    depth = 1
    while depth:
        depth += (source[offset] == "{") - (source[offset] == "}")
        offset += 1
    return source[match.start() : offset]


assert "esp_err_t session_graph_init(void);" in HEADER
assert "bool session_graph_cancel_and_wait(void);" in HEADER
assert re.search(r"#define\s+SNT_QUEUE_DEPTH\s+1\b", GRAPH)
assert re.search(r"#define\s+SNT_MAX_INFLIGHT\s+2\b", GRAPH)

for public, implementation in (
    ("sessions_list_handler", "sessions_list_handler_impl"),
    ("days_list_handler", "days_list_handler_impl"),
    ("summary_handler", "summary_handler_impl"),
    ("session_settings_handler", "session_settings_handler_impl"),
    ("session_graph_handler", "session_graph_handler_impl"),
):
    wrapper = function(GRAPH, public)
    assert f"session_graph_with_storage(req, {implementation})" in wrapper
    assert "session_graph_storage_cancelled()" in function(GRAPH, implementation)

storage = function(GRAPH, "session_graph_with_storage")
assert "session_graph_request_begin()" in storage
assert "sd_storage_lease_acquire(SD_LEASE_UPLOAD, 0)" in storage
assert "session_graph_storage_cancelled()" in storage
assert "sd_storage_lease_release_unchanged(SD_LEASE_UPLOAD)" in storage
assert "session_graph_request_end()" in storage

file_wrapper = function(GRAPH, "session_file_handler")
assert "session_graph_request_begin()" in file_wrapper
assert "session_file_handler_impl(req)" in file_wrapper
assert "session_graph_request_end()" in file_wrapper

admit = function(GRAPH, "snt_download_admit")
assert "s_graph_closing" in admit
assert "portENTER_CRITICAL(&s_graph_state_lock)" in admit
assert "SNT_MAX_INFLIGHT" in admit
assert "__atomic_add_fetch(&s_download_inflight" in admit

send = function(GRAPH, "snt_send_file")
lease_at = send.index("sd_storage_lease_acquire(SD_LEASE_UPLOAD, 0)")
open_at = send.index("fopen(transfer->file_path")
loop_at = send.index("while (remaining > 0)")
cancel_at = send.index("snt_download_cancelled()", loop_at)
close_at = send.rindex("fclose(f)")
release_at = send.rindex("sd_storage_lease_release_unchanged(SD_LEASE_UPLOAD)")
assert lease_at < open_at < loop_at < cancel_at < close_at < release_at

worker = function(GRAPH, "snt_download_worker")
complete_at = worker.index("httpd_req_async_handler_complete(transfer->req)")
release_at = worker.index("snt_download_release()")
assert "shutdown(httpd_req_to_sockfd(transfer->req), SHUT_RDWR)" in worker
assert complete_at < release_at

cancel = function(GRAPH, "session_graph_cancel_and_wait")
closing_at = cancel.index("s_graph_closing")
wait_at = cancel.index("s_download_inflight")
assert closing_at < wait_at
assert "s_sync_inflight" in cancel
assert "return false" in cancel and "return true" in cancel

start = function(NET, "start_webserver")
stop_at = start.index("httpd_stop(s_httpd)")
assert start.index("session_graph_cancel_and_wait()") < stop_at
init_at = start.index("session_graph_init()")
httpd_start_at = start.index("httpd_start(&s_httpd")
register_at = start.index(".handler = session_file_handler")
assert init_at < httpd_start_at < register_at
assert "if (graph_err != ESP_OK)" in start

print("session graph lifecycle contract passed")
