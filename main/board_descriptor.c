#include "board_descriptor.h"

#include "sdkconfig.h"

#if CONFIG_SOMNOTRACE_BOARD_WAVESHARE_7B
static const somnotrace_board_descriptor_t s_board = {
    .firmware_target = SOMNOTRACE_FIRMWARE_TARGET_ID,
    .platform = SOMNOTRACE_PLATFORM_PHYSICAL,
    .display = SOMNOTRACE_DISPLAY_TOUCH_1024,
    .transport = SOMNOTRACE_DISPLAY_TRANSPORT_RGB_FRAME,
    .width = 1024,
    .height = 600,
    .capabilities = SOMNOTRACE_CAP_TOUCH | SOMNOTRACE_CAP_BACKLIGHT_LEVEL |
                    SOMNOTRACE_CAP_RGB_FRAME_RETIRE | SOMNOTRACE_CAP_SHARED_DISPLAY_SD_IO,
};
#elif CONFIG_SOMNOTRACE_BOARD_QEMU && CONFIG_SOMNOTRACE_QEMU_DISPLAY_154
static const somnotrace_board_descriptor_t s_board = {
    .firmware_target = SOMNOTRACE_FIRMWARE_TARGET_ID,
    .platform = SOMNOTRACE_PLATFORM_EMULATOR,
    .display = SOMNOTRACE_DISPLAY_COMPACT_240,
    .transport = SOMNOTRACE_DISPLAY_TRANSPORT_RGB_FRAME,
    .width = 240,
    .height = 240,
    .capabilities = SOMNOTRACE_CAP_RGB_FRAME_RETIRE,
};
#elif CONFIG_SOMNOTRACE_BOARD_QEMU
static const somnotrace_board_descriptor_t s_board = {
    .firmware_target = SOMNOTRACE_FIRMWARE_TARGET_ID,
    .platform = SOMNOTRACE_PLATFORM_EMULATOR,
    .display = SOMNOTRACE_DISPLAY_TOUCH_1024,
    .transport = SOMNOTRACE_DISPLAY_TRANSPORT_RGB_FRAME,
    .width = 1024,
    .height = 600,
    .capabilities = SOMNOTRACE_CAP_TOUCH | SOMNOTRACE_CAP_RGB_FRAME_RETIRE,
};
#else
static const somnotrace_board_descriptor_t s_board = {
    .firmware_target = SOMNOTRACE_FIRMWARE_TARGET_ID,
    .platform = SOMNOTRACE_PLATFORM_PHYSICAL,
    .display = SOMNOTRACE_DISPLAY_COMPACT_240,
    .transport = SOMNOTRACE_DISPLAY_TRANSPORT_SPI_PUSH,
    .width = 240,
    .height = 240,
    .capabilities = SOMNOTRACE_CAP_TOUCH | SOMNOTRACE_CAP_BACKLIGHT_LEVEL | SOMNOTRACE_CAP_AUDIO,
};
#endif

const somnotrace_board_descriptor_t *somnotrace_board_descriptor(void)
{
    return &s_board;
}

bool somnotrace_board_has(uint32_t capability)
{
    return (s_board.capabilities & capability) == capability;
}
