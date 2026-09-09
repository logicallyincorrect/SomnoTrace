#pragma once

#include "esp_err.h"
#include "touch_observation.h"

/* Retained input sampling is owned by the selected platform. UI consumers
 * receive copies so controller recovery cannot race LVGL reads. */
esp_err_t touch_input_start(void);
void touch_input_snapshot(touch_observation_t *out);
