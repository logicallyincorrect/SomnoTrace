#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "sdkconfig.h"

typedef enum {
    SOMNOTRACE_PLATFORM_PHYSICAL,
    SOMNOTRACE_PLATFORM_EMULATOR,
} somnotrace_platform_kind_t;

typedef enum {
    SOMNOTRACE_DISPLAY_COMPACT_240,
    SOMNOTRACE_DISPLAY_TOUCH_1024,
} somnotrace_display_profile_t;

typedef enum {
    SOMNOTRACE_DISPLAY_TRANSPORT_SPI_PUSH,
    SOMNOTRACE_DISPLAY_TRANSPORT_RGB_FRAME,
} somnotrace_display_transport_t;

enum {
    SOMNOTRACE_CAP_TOUCH = 1U << 0,
    SOMNOTRACE_CAP_BACKLIGHT_LEVEL = 1U << 1,
    SOMNOTRACE_CAP_RGB_FRAME_RETIRE = 1U << 2,
    SOMNOTRACE_CAP_SHARED_DISPLAY_SD_IO = 1U << 3,
    SOMNOTRACE_CAP_AUDIO = 1U << 4,
};

typedef struct {
    const char *firmware_target;
    somnotrace_platform_kind_t platform;
    somnotrace_display_profile_t display;
    somnotrace_display_transport_t transport;
    uint16_t width;
    uint16_t height;
    uint32_t capabilities;
} somnotrace_board_descriptor_t;

#if CONFIG_SOMNOTRACE_BOARD_WAVESHARE_7B
#define SOMNOTRACE_FIRMWARE_TARGET_ID "waveshare-7b"
#elif CONFIG_SOMNOTRACE_BOARD_QEMU && CONFIG_SOMNOTRACE_QEMU_DISPLAY_154
#define SOMNOTRACE_FIRMWARE_TARGET_ID "qemu-154"
#elif CONFIG_SOMNOTRACE_BOARD_QEMU
#define SOMNOTRACE_FIRMWARE_TARGET_ID "qemu-ui"
#else
#define SOMNOTRACE_FIRMWARE_TARGET_ID "waveshare-154"
#endif

const somnotrace_board_descriptor_t *somnotrace_board_descriptor(void);
bool somnotrace_board_has(uint32_t capability);
