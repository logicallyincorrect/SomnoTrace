#include "touch_display_handoff.h"

#include <string.h>

#include "controller_diagnostics.h"
#include "display_profile_touch.h"
#include "esp_log.h"
#include "sdkconfig.h"

static const char *TAG = "display_handoff";

void touch_display_handoff_init(touch_display_handoff_t *handoff)
{
    if (handoff)
        memset(handoff, 0, sizeof(*handoff));
}

void touch_display_handoff_set_render_task(touch_display_handoff_t *handoff, TaskHandle_t task)
{
    if (handoff)
        handoff->render_task = task;
}

bool IRAM_ATTR touch_display_handoff_frame_complete(esp_lcd_panel_handle_t panel,
                                                    const esp_lcd_rgb_panel_event_data_t *event,
                                                    void *context)
{
    (void)panel;
    (void)event;
    touch_display_handoff_t *handoff = context;
    BaseType_t wake = pdFALSE;
    if (handoff && handoff->render_task)
        vTaskNotifyGiveFromISR(handoff->render_task, &wake);
    return wake == pdTRUE;
}

#if !CONFIG_SOMNOTRACE_BOARD_QEMU
static void submit_rgb_frame(touch_display_handoff_t *handoff,
                             lv_disp_drv_t *driver,
                             lv_color_t *pixels)
{
    esp_lcd_panel_handle_t panel = (esp_lcd_panel_handle_t)driver->user_data;
    for (;;) {
        esp_err_t result = esp_lcd_panel_draw_bitmap(
            panel, 0, 0, SOMNOTRACE_TOUCH_DISPLAY_WIDTH, SOMNOTRACE_TOUCH_DISPLAY_HEIGHT, pixels);
        controller_diagnostics_record(CONTROLLER_PANEL_SUBMIT, result);
        if (result == ESP_OK)
            break;
        handoff->timeouts++;
        ESP_LOGE(TAG, "RGB frame submission failed: %s", esp_err_to_name(result));
        /* LVGL must retain this buffer until a submission succeeds. */
        vTaskDelay(pdMS_TO_TICKS(100));
    }

    /* Clear stale EOFs after the new scanout buffer was selected. An EOF
     * between a pre-submit clear and draw_bitmap belongs to the old frame. */
    ulTaskNotifyTake(pdTRUE, 0);
    while (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(100)) == 0) {
        controller_diagnostics_record(CONTROLLER_PANEL_HANDOFF, ESP_ERR_TIMEOUT);
        handoff->timeouts++;
        if (handoff->timeouts == 1 || (handoff->timeouts % 100) == 0)
            ESP_LOGW(TAG,
                     "RGB handoff delayed (%lu); retaining framebuffer",
                     (unsigned long)handoff->timeouts);
        (void)esp_lcd_rgb_panel_restart(panel);
    }
    controller_diagnostics_record(CONTROLLER_PANEL_HANDOFF, ESP_OK);
}
#endif

bool touch_display_handoff_flush(touch_display_handoff_t *handoff,
                                 lv_disp_drv_t *driver,
                                 lv_color_t *pixels)
{
    if (!handoff || !driver)
        return false;
    if (!lv_disp_flush_is_last(driver)) {
        lv_disp_flush_ready(driver);
        return false;
    }

#if CONFIG_SOMNOTRACE_BOARD_QEMU
    esp_err_t submitted = esp_lcd_panel_draw_bitmap((esp_lcd_panel_handle_t)driver->user_data,
                                                    0,
                                                    0,
                                                    SOMNOTRACE_TOUCH_DISPLAY_WIDTH,
                                                    SOMNOTRACE_TOUCH_DISPLAY_HEIGHT,
                                                    pixels);
    controller_diagnostics_record(CONTROLLER_PANEL_SUBMIT, submitted);
    if (submitted != ESP_OK) {
        handoff->timeouts++;
        ESP_LOGE(TAG, "RGB frame submission failed: %s", esp_err_to_name(submitted));
        lv_disp_flush_ready(driver);
        return false;
    }
#else
    submit_rgb_frame(handoff, driver, pixels);
#endif

    handoff->frames++;
    lv_disp_flush_ready(driver);
    return true;
}

void touch_display_handoff_snapshot(const touch_display_handoff_t *handoff,
                                    touch_display_handoff_snapshot_t *snapshot)
{
    if (!snapshot)
        return;
    if (!handoff) {
        memset(snapshot, 0, sizeof(*snapshot));
        return;
    }
    snapshot->frames = handoff->frames;
    snapshot->timeouts = handoff->timeouts;
}
