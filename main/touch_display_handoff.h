#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_rgb.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lvgl.h"

typedef struct {
    TaskHandle_t render_task;
    uint32_t frames;
    uint32_t timeouts;
} touch_display_handoff_t;

typedef struct {
    uint32_t frames;
    uint32_t timeouts;
} touch_display_handoff_snapshot_t;

void touch_display_handoff_init(touch_display_handoff_t *handoff);
void touch_display_handoff_set_render_task(touch_display_handoff_t *handoff, TaskHandle_t task);
bool touch_display_handoff_frame_complete(esp_lcd_panel_handle_t panel,
                                          const esp_lcd_rgb_panel_event_data_t *event,
                                          void *context);

/* Completes the LVGL flush callback and returns true only when a complete
 * composition frame was published. */
bool touch_display_handoff_flush(touch_display_handoff_t *handoff,
                                 lv_disp_drv_t *driver,
                                 lv_color_t *pixels);
void touch_display_handoff_snapshot(const touch_display_handoff_t *handoff,
                                    touch_display_handoff_snapshot_t *snapshot);
