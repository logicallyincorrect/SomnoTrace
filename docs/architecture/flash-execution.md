# Flash execution

SomnoTrace creates one retained FreeRTOS task with an 8 KiB internal-RAM stack
during boot. Short NVS, partition, and OTA operations run synchronously on that
task through `flash_executor_run()`. Network reads, TLS, filesystem access, and
other long work stay on their PSRAM-backed caller tasks.

This is a cache-safety boundary. A callback must copy its control fields from
caller-owned memory into local variables before calling an API that disables
the SPI cache. It must not call the executor recursively, acquire the executor
lock, wait for input, or retain pointers after it returns.

OTA upload, URL, and SD paths share `ota_flash_session`:

1. Validate the 384-byte board identity before beginning the inactive image.
2. Check therapy/cancellation before each queued write and again inside the
   executor callback.
3. Finish image validation, then check cancellation again.
4. Reserve the maintenance commit before selecting the boot partition.
5. Use the therapy-aware restart path after selection.

The HTTP upload handler streams directly from its PSRAM request buffer. URL and
SD readers run as reclaimable PSRAM tasks. No OTA path allocates another
internal-RAM task stack at request time.
