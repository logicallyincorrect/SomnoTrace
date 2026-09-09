#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "display_profile_touch.h"
#include "esp_err.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_touch.h"

/* Compile-selected RGB transport used by the touch renderer. Physical boards
 * and emulators implement this contract independently. */
esp_err_t rgb_display_transport_init(esp_lcd_panel_handle_t *panel, esp_lcd_touch_handle_t *touch);
esp_err_t rgb_display_transport_set_backlight(bool on);
esp_err_t rgb_display_transport_set_brightness_percent(uint8_t percent);
esp_err_t rgb_display_transport_set_pixel_clock(uint32_t hz);
esp_err_t rgb_display_transport_reassert_visible(void);
void rgb_display_transport_set_recovery_brightness(uint8_t percent);
