#pragma once

#include_next <string.h>

/* ESP-IDF and BSD libc provide strlcpy. glibc does not, so production-source
 * extraction tests get the same bounded-copy contract through this host shim. */
#if !defined(__APPLE__) && !defined(__FreeBSD__)
static inline size_t strlcpy(char *destination, const char *source, size_t size)
{
    size_t length = strlen(source);
    if (size) {
        size_t copied = length < size - 1 ? length : size - 1;
        memcpy(destination, source, copied);
        destination[copied] = '\0';
    }
    return length;
}
#endif
