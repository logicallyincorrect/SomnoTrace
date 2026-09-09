/* ESP32-S3 QEMU virtual panel adapter for the 1024x600 SomnoTrace UI. */
#include "display_transport_rgb.h"
#include "touch_input.h"
#include "board_qemu.h"
#include "controller_diagnostics.h"

#include "esp_check.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_qemu_rgb.h"
#include "esp_log.h"

static const char *TAG = "board_qemu";

#define QEMU_RGB_TOUCH_POSITION (*(volatile uint32_t *)0x2100001c)
#define QEMU_RGB_TOUCH_STATUS (*(volatile uint32_t *)0x21000020)

void board_qemu_touch_read(uint16_t *x, uint16_t *y, bool *pressed)
{
    static bool was_pressed;
    uint32_t position = QEMU_RGB_TOUCH_POSITION;
    *x = (uint16_t)(position >> 16);
    *y = (uint16_t)position;
    *pressed = (QEMU_RGB_TOUCH_STATUS & 1U) != 0;
    /* Test drivers must wait for an observed release before the next press.
     * Wall-clock delays alone coalesce taps during a slow guest redraw. */
    if (was_pressed && !*pressed)
        ESP_LOGI(TAG, "QEMU touch release sampled");
    was_pressed = *pressed;
}

esp_err_t rgb_display_transport_init(esp_lcd_panel_handle_t *panel, esp_lcd_touch_handle_t *touch)
{
    ESP_RETURN_ON_FALSE(
        panel && touch, ESP_ERR_INVALID_ARG, TAG, "panel/touch outputs are required");
    *touch = NULL;
    esp_lcd_rgb_qemu_config_t config = {
        .width = SOMNOTRACE_TOUCH_DISPLAY_WIDTH,
        .height = SOMNOTRACE_TOUCH_DISPLAY_HEIGHT,
        .bpp = RGB_QEMU_BPP_16,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_rgb_qemu(&config, panel), TAG, "create QEMU RGB panel");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_reset(*panel), TAG, "reset QEMU panel");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_init(*panel), TAG, "initialize QEMU panel");
    return ESP_OK;
}

esp_err_t rgb_display_transport_set_backlight(bool on)
{
    (void)on;
    controller_diagnostics_record(CONTROLLER_BACKLIGHT_POWER, ESP_OK);
    return ESP_OK;
}

esp_err_t rgb_display_transport_set_brightness_percent(uint8_t percent)
{
    (void)percent;
    controller_diagnostics_record(CONTROLLER_BACKLIGHT_BRIGHTNESS, ESP_OK);
    return ESP_OK;
}
