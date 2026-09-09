#!/usr/bin/env python3
"""Compile the board descriptor for every supported platform/profile."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

PROFILES = (
    ("waveshare-154", 0, 0, 240, 240, "SOMNOTRACE_DISPLAY_COMPACT_240"),
    ("waveshare-7b", 1, 0, 1024, 600, "SOMNOTRACE_DISPLAY_TOUCH_1024"),
    ("qemu-ui", 0, 1, 1024, 600, "SOMNOTRACE_DISPLAY_TOUCH_1024"),
    ("qemu-154", 0, 2, 240, 240, "SOMNOTRACE_DISPLAY_COMPACT_240"),
)

TEST_SOURCE = r'''#include <assert.h>
#include <string.h>
#include "board_descriptor.h"

int main(void)
{
    const somnotrace_board_descriptor_t *board = somnotrace_board_descriptor();
    assert(strcmp(board->firmware_target, EXPECTED_TARGET) == 0);
    assert(board->width == EXPECTED_WIDTH);
    assert(board->height == EXPECTED_HEIGHT);
    assert(board->display == EXPECTED_DISPLAY);
    assert(somnotrace_board_has(board->capabilities));
    return 0;
}
'''

with tempfile.TemporaryDirectory() as temp:
    work = Path(temp)
    (work / "test.c").write_text(TEST_SOURCE)
    for target, physical_7b, qemu_kind, width, height, display in PROFILES:
        qemu = int(qemu_kind != 0)
        qemu_154 = int(qemu_kind == 2)
        (work / "sdkconfig.h").write_text(
            f"#define CONFIG_SOMNOTRACE_BOARD_WAVESHARE_7B {physical_7b}\n"
            f"#define CONFIG_SOMNOTRACE_BOARD_QEMU {qemu}\n"
            f"#define CONFIG_SOMNOTRACE_QEMU_DISPLAY_154 {qemu_154}\n"
        )
        output = work / target
        subprocess.run(
            [
                "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-I", str(work), "-I", str(ROOT / "main"),
                f'-DEXPECTED_TARGET="{target}"',
                f"-DEXPECTED_WIDTH={width}", f"-DEXPECTED_HEIGHT={height}",
                f"-DEXPECTED_DISPLAY={display}",
                str(work / "test.c"), str(ROOT / "main/board_descriptor.c"),
                "-o", str(output),
            ],
            check=True,
        )
        subprocess.run([str(output)], check=True, timeout=5)

print("Board descriptors: compact, 7B, QEMU touch and QEMU compact passed")
