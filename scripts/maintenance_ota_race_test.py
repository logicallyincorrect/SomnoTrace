#!/usr/bin/env python3
"""Execute production cancel/commit gate code with deterministic host state."""
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
net=(ROOT/'main/net_provision.c').read_text()
display=(ROOT/'main/bsp_display_7b.c').read_text()
def function(source,name):
    match=re.search(rf'^\s*[\w][\w\s*]*\b{name}\s*\([^;{{}}]*\)\s*\{{',source,re.M)
    assert match,name
    depth=1; cursor=match.end()
    while depth:
        if source[cursor]=='{':depth+=1
        elif source[cursor]=='}':depth-=1
        cursor+=1
    return source[match.start():cursor]
code=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include "therapy_gate.h"
static int s_state_lock,s_ota_progress_lock,locked;
#define portENTER_CRITICAL(p) do { (void)(p); assert(!locked); locked=1; } while(0)
#define portEXIT_CRITICAL(p) do { (void)(p); assert(locked); locked=0; } while(0)
static therapy_gate_t s_therapy_gate = THERAPY_GATE_INITIALIZER;
#define MAINT_OTA_COMMIT 3
static struct {bool active,cancellable,cancel_requested;int stage;} s_ota_progress;
'''
for src,name in ((display,'bsp_display_try_reserve_maintenance_commit'),
                 (display,'bsp_display_cancel_therapy_safe_restart'),
                 (net,'maintenance_ota_cancel'),(net,'ota_native_commit_begin')):
    code+='\n'+function(src,name)+'\n'
code+=r'''
static void reset(void) {
    s_therapy_gate=(therapy_gate_t)THERAPY_GATE_INITIALIZER;
    memset(&s_ota_progress,0,sizeof(s_ota_progress));
    assert(therapy_gate_try_begin_maintenance(&s_therapy_gate));
    s_ota_progress.active=s_ota_progress.cancellable=true;
}
int main(void) {
    reset();assert(maintenance_ota_cancel());assert(!ota_native_commit_begin());
    assert(!therapy_gate_restart_is_reserving(&s_therapy_gate));
    reset();assert(ota_native_commit_begin());assert(!maintenance_ota_cancel());
    assert(therapy_gate_restart_is_reserving(&s_therapy_gate));assert(!s_ota_progress.cancellable);
    bsp_display_cancel_therapy_safe_restart();assert(!therapy_gate_restart_is_reserving(&s_therapy_gate));
    reset();assert(therapy_gate_try_set_active(&s_therapy_gate,true));assert(!ota_native_commit_begin());assert(maintenance_ota_cancel());
    reset();assert(therapy_gate_try_reserve_start(&s_therapy_gate));assert(!ota_native_commit_begin());
    reset();therapy_gate_note_start_waiter(&s_therapy_gate);assert(!ota_native_commit_begin());
    reset();therapy_gate_note_notification_queued(&s_therapy_gate);assert(!ota_native_commit_begin());
    reset();therapy_gate_end_maintenance(&s_therapy_gate);assert(therapy_gate_try_reserve_restart(&s_therapy_gate));assert(therapy_gate_try_commit_restart(&s_therapy_gate));assert(!ota_native_commit_begin());
    reset();therapy_gate_end_maintenance(&s_therapy_gate);assert(!ota_native_commit_begin());
    reset();s_ota_progress.active=false;assert(!maintenance_ota_cancel());
    assert(!locked);puts("production OTA cancel/therapy/commit interleavings passed");
}
'''
with tempfile.TemporaryDirectory(prefix='somno-ota-race-') as path:
    source=Path(path)/'race.c';binary=Path(path)/'race';source.write_text(code)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'main'),
                    str(source),str(ROOT/'main/therapy_gate.c'),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
# Full factory erasure commits its one-way restart before NVS and never returns
# from that branch, including an erase failure.
factory=function(net,'factory_reset_task')
assert factory.index('bsp_display_try_commit_therapy_safe_restart()') < factory.index('flash_executor_lock()') < factory.index('nvs_flash_erase()') < factory.index('esp_restart()')
assert 'flash_executor_unlock()' not in factory
assert factory.index('esp_restart()') < factory.index('out:')
sd=function(net,'ota_sd_task')
assert sd.index('somnotrace_firmware_target_matches') < sd.index('ota_flash_session_begin(')
assert sd.index('ota_flash_session_finish(') < sd.index('ota_native_commit_begin()') < sd.index('ota_flash_session_select(')
assert 'ota_sd_flash_should_abort' in sd
assert 'sd_storage_recording_pending()' in function(net,'ota_sd_flash_should_abort')
print('factory reset and SD image boundary contracts passed')
