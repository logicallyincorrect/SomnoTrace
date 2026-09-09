# Display platform architecture

SomnoTrace supports two renderer profiles:

- `compact-240`: the original 240 x 240 retained framebuffer UI.
- `touch-1024`: the 1024 x 600 LVGL UI.

They are separate products of the same application model. The large renderer
must not be scaled down to produce the compact UI, and an emulator must not
impersonate a physical board.

## Dependency direction

Application services publish state through `bsp_display.h`. A renderer owns
layout and widgets. A display transport owns frame submission and retirement.
A platform owns GPIO, controller recovery, touch sampling, and shared IO.

```text
application services
        |
display facade + therapy gate
        |
renderer profile (compact-240 | touch-1024)
        |
typed transport (SPI push | RGB frame retirement)
        |
platform (Waveshare 1.54 | Waveshare 7B | QEMU)
```

`board_descriptor.h` is the compile-selected description of platform kind,
renderer, transport, geometry, OTA identity, and capabilities. OTA target
strings are compatibility data and must remain byte-for-byte stable.

`display_transport_rgb.h`, `touch_input.h`, and `board_storage.h` are platform
contracts. `board_waveshare_7b.c` and `board_qemu.c` implement those contracts
independently. The QEMU implementation does not include or export Waveshare
symbols.

`therapy_gate.c` owns therapy, restart, notification, and maintenance admission
state. Renderers only mirror therapy state for presentation. Screen choice can
never determine whether therapy is active.

`touch_display_handoff.c` owns RGB buffer submission and positive frame
retirement. Do not release an LVGL buffer after a timeout: only the panel EOF
callback proves that scanout retired it.

`touch_keyboard_maps.c` owns LVGL 8 keyboard map lifecycle. LVGL stores maps
globally by mode, so every surface reapplies its layout immediately before the
keyboard is shown or changes mode.

## Adding a board

1. Add one board selection and one descriptor. Choose an existing renderer and
   transport where possible.
2. Implement the selected transport and explicit capabilities. Unsupported
   hardware operations return `ESP_ERR_NOT_SUPPORTED`; silent no-ops are not a
   capability contract.
3. Assign a new firmware target string. Never reuse a physical target for an
   emulator or another board.
4. Add the descriptor host case, an ESP-IDF build profile, and a QEMU profile
   when the transport can be emulated.
5. Preserve physical recovery ordering as a single platform-owned subsystem.
   On the 7B this includes CH32 output locking, backlight generations, GT911
   reset fences, and SD pin arbitration.

## Accepted follow-up work

The current boundary is a safe first extraction, not the end state.

- Split the remaining `bsp_display_7b.c` page trees into shell, Home, Devices,
  presenter, setup, and preview modules with explicit context structs.
- Split History storage/index/cache/model work from its renderer. Keep exact
  percentiles separate from min/max envelope caches.
- Split HTTP lifecycle and downloads out of `net_provision.c`.
- Replace the root-level LVGL target mutation with a supported allocator
  configuration once the managed component exposes allocator symbols through
  Kconfig or a public component dependency.
- Consolidate QEMU process/QMP/provenance code into one harness.
- Lock font generation tools in a container and add UTF-8/input schemas before
  expanding localized UI text.

Generated fonts and vendored sources are excluded from project formatting.
Authored C and headers use the pinned `clang-format` version enforced in CI.
