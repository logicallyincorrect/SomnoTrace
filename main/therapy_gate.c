/*
 * SomnoTrace renderer-neutral therapy state.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include "therapy_gate.h"

bool therapy_gate_try_set_active(therapy_gate_t *gate, bool active)
{
    if (!gate || (active && (gate->restart_reserving || gate->restart_committed))) {
        return false;
    }
    gate->active = active;
    return true;
}

bool therapy_gate_is_active(const therapy_gate_t *gate)
{
    return gate && gate->active;
}

bool therapy_gate_restart_is_reserving(const therapy_gate_t *gate)
{
    return gate && gate->restart_reserving;
}

void therapy_gate_note_start_waiter(therapy_gate_t *gate)
{
    if (gate)
        gate->start_waiters++;
}

void therapy_gate_remove_start_waiter(therapy_gate_t *gate)
{
    if (gate && gate->start_waiters > 0)
        gate->start_waiters--;
}

bool therapy_gate_try_reserve_restart(therapy_gate_t *gate)
{
    if (!gate || gate->active || gate->start_claims > 0 || gate->start_waiters > 0 ||
        gate->notifications_pending > 0 || gate->maintenance || gate->restart_reserving ||
        gate->restart_committed) {
        return false;
    }
    gate->restart_reserving = true;
    return true;
}

bool therapy_gate_try_commit_restart(therapy_gate_t *gate)
{
    if (!gate || !gate->restart_reserving || gate->active || gate->start_waiters > 0 ||
        gate->notifications_pending > 0) {
        return false;
    }
    gate->restart_reserving = false;
    gate->restart_committed = true;
    return true;
}

void therapy_gate_cancel_restart(therapy_gate_t *gate)
{
    if (gate && !gate->restart_committed)
        gate->restart_reserving = false;
}

bool therapy_gate_try_reserve_start(therapy_gate_t *gate)
{
    if (!gate || gate->restart_reserving || gate->restart_committed) {
        return false;
    }
    gate->start_claims++;
    return true;
}

void therapy_gate_release_start(therapy_gate_t *gate)
{
    if (gate && gate->start_claims > 0)
        gate->start_claims--;
}

void therapy_gate_note_notification_queued(therapy_gate_t *gate)
{
    if (gate)
        gate->notifications_pending++;
}

void therapy_gate_note_notification_processed(therapy_gate_t *gate)
{
    if (gate && gate->notifications_pending > 0) {
        gate->notifications_pending--;
    }
}

bool therapy_gate_try_begin_maintenance(therapy_gate_t *gate)
{
    if (!gate || gate->active || gate->start_claims > 0 || gate->start_waiters > 0 ||
        gate->notifications_pending > 0 || gate->maintenance || gate->restart_reserving ||
        gate->restart_committed) {
        return false;
    }
    gate->maintenance = true;
    return true;
}

bool therapy_gate_try_reserve_maintenance_commit(therapy_gate_t *gate)
{
    if (!gate || !gate->maintenance || gate->active || gate->start_claims > 0 ||
        gate->start_waiters > 0 || gate->notifications_pending > 0 || gate->restart_reserving ||
        gate->restart_committed) {
        return false;
    }
    gate->maintenance = false;
    gate->restart_reserving = true;
    return true;
}

bool therapy_gate_maintenance_should_abort(const therapy_gate_t *gate)
{
    return !gate || !gate->maintenance || gate->active || gate->start_claims > 0 ||
           gate->start_waiters > 0;
}

void therapy_gate_end_maintenance(therapy_gate_t *gate)
{
    if (gate)
        gate->maintenance = false;
}
