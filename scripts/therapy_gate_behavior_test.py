#!/usr/bin/env python3
"""Exercise renderer-neutral therapy state and compact restart gates."""
from pathlib import Path
import re, subprocess, tempfile
ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'main/bsp_display.c').read_text()
def function(name):
    m = re.search(r'^(?:static\s+)?[\w *]+\b'+name+r'\([^;{]*\)\s*\{', source, re.M)
    assert m, name
    i, depth = m.end(), 1
    while depth:
        depth += (source[i] == '{') - (source[i] == '}'); i += 1
    return source[m.start():i]
names = ['try_reserve_therapy_safe_restart', 'try_commit_therapy_safe_restart',
         'cancel_therapy_safe_restart', 'reserve_therapy_start', 'release_therapy_start',
         'note_as11_notification_queued', 'note_as11_notification_processed',
         'try_begin_therapy_safe_maintenance', 'try_reserve_maintenance_commit',
         'therapy_safe_maintenance_should_abort', 'end_therapy_safe_maintenance',
         'is_therapy_active']
setter = function('bsp_display_set_therapy_active')
assert 'dev->therapy_screen == THERAPY_SCREEN_STATUS' in setter
assert 'therapy_gate_try_set_active(&s_therapy_gate, active)' in setter
fixture = '''#include <assert.h>
#include <stdbool.h>
#include "therapy_gate.h"
#define portMAX_DELAY 0
#define DISP_MODE_STATUS 0
#define DISP_MODE_GRAPH 1
#define DISP_MODE_INFO 2
static int s_state_mutex = 1, s_mode;
static therapy_gate_t s_therapy_gate = THERAPY_GATE_INITIALIZER;
static int locked;
static void xSemaphoreTake(int m, int t) { assert(m && !locked); locked = 1; }
static void xSemaphoreGive(int m) { assert(m && locked); locked = 0; }
static void vTaskDelay(int t) { assert(!"unexpected blocking gate"); }
'''+ '\n'.join(function('bsp_display_'+n) for n in names) + '''
int main(void) {
    therapy_gate_t isolated = THERAPY_GATE_INITIALIZER;
    assert(therapy_gate_try_reserve_restart(&isolated));
    assert(!therapy_gate_try_set_active(&isolated, true));
    assert(!therapy_gate_try_reserve_start(&isolated));
    therapy_gate_cancel_restart(&isolated);
    assert(therapy_gate_try_set_active(&isolated, true));

    assert(bsp_display_try_reserve_therapy_safe_restart());
    bsp_display_note_as11_notification_queued();
    assert(!bsp_display_try_commit_therapy_safe_restart());
    bsp_display_cancel_therapy_safe_restart();
    assert(!bsp_display_try_reserve_therapy_safe_restart());
    bsp_display_note_as11_notification_processed();
    assert(bsp_display_reserve_therapy_start());
    assert(!bsp_display_try_reserve_therapy_safe_restart());
    bsp_display_release_therapy_start();
    assert(bsp_display_try_begin_therapy_safe_maintenance());
    /* STATUS is a presentation choice. It must not make active therapy safe
     * for maintenance or restart. This was the compact-display regression. */
    s_mode = DISP_MODE_STATUS;
    assert(therapy_gate_try_set_active(&s_therapy_gate, true));
    assert(bsp_display_is_therapy_active());
    assert(bsp_display_therapy_safe_maintenance_should_abort());
    assert(!bsp_display_try_reserve_maintenance_commit());
    s_mode = DISP_MODE_INFO;
    assert(bsp_display_therapy_safe_maintenance_should_abort());
    assert(!bsp_display_try_reserve_maintenance_commit());
    s_mode = DISP_MODE_GRAPH;
    assert(!bsp_display_try_reserve_maintenance_commit());
    assert(therapy_gate_try_set_active(&s_therapy_gate, false));
    s_mode = DISP_MODE_STATUS;
    assert(bsp_display_try_reserve_maintenance_commit());
    assert(bsp_display_try_commit_therapy_safe_restart());
    assert(!bsp_display_reserve_therapy_start());
    assert(!locked);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp); (p/'test.c').write_text(fixture)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',
                    '-Wno-unused-parameter','-I',str(ROOT/'main'),str(p/'test.c'),
                    str(ROOT/'main/therapy_gate.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True,timeout=5)
print('Renderer-neutral therapy gate: STATUS, graph/info, pending RX, start claims and final commit passed')
