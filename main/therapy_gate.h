/*
 * SomnoTrace renderer-neutral therapy state.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#pragma once

#include <stdbool.h>

typedef struct {
    bool active;
    bool restart_reserving;
    bool restart_committed;
    unsigned start_waiters;
    unsigned start_claims;
    unsigned notifications_pending;
    bool maintenance;
} therapy_gate_t;

#define THERAPY_GATE_INITIALIZER {0}

/* Synchronization is owned by the caller so therapy publication and the
 * restart/maintenance decisions that consume it remain one atomic operation. */
bool therapy_gate_try_set_active(therapy_gate_t *gate, bool active);
bool therapy_gate_is_active(const therapy_gate_t *gate);
bool therapy_gate_restart_is_reserving(const therapy_gate_t *gate);
void therapy_gate_note_start_waiter(therapy_gate_t *gate);
void therapy_gate_remove_start_waiter(therapy_gate_t *gate);
bool therapy_gate_try_reserve_restart(therapy_gate_t *gate);
bool therapy_gate_try_commit_restart(therapy_gate_t *gate);
void therapy_gate_cancel_restart(therapy_gate_t *gate);
bool therapy_gate_try_reserve_start(therapy_gate_t *gate);
void therapy_gate_release_start(therapy_gate_t *gate);
void therapy_gate_note_notification_queued(therapy_gate_t *gate);
void therapy_gate_note_notification_processed(therapy_gate_t *gate);
bool therapy_gate_try_begin_maintenance(therapy_gate_t *gate);
bool therapy_gate_try_reserve_maintenance_commit(therapy_gate_t *gate);
bool therapy_gate_maintenance_should_abort(const therapy_gate_t *gate);
void therapy_gate_end_maintenance(therapy_gate_t *gate);
