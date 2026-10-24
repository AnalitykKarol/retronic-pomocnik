/* Exact candidate predicate from Pamiec._kandydaci_stworow, ABI 1.
 * Input is borrowed for this call; returned offsets belong to the caller.
 * No global mutable state. Built only for little-endian 64-bit x86 hosts. */
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

uint32_t skan_abi(void) { return 1; }

static inline uint32_t rd(const unsigned char *p) {
    uint32_t x;
    memcpy(&x, p, sizeof(x)); /* also safe for an unaligned Python buffer */
    return x;
}

int scan(const unsigned char *b, size_t len, uint64_t **out, size_t *count) {
    *out = NULL;
    *count = 0;
    size_t n = len / 4, capacity = 0;
    if (n < 12) return 0;
    /* Preserve the original n-11 upper bound, including its final padding. */
    for (size_t i = 0; i < n - 11; i++) {
        const unsigned char *p = b + 4 * i;
        if (rd(p + 40) != 15) continue;
        uint32_t size = rd(p + 36);
        if (size < 1 || size > 15) continue;
        uint32_t id = rd(p + 16) >> 24;
        if (id < 0x10 || id > 0x4f) continue;
        if (rd(p) != 0x3f800000 || rd(p + 4) != 0x3f800000 ||
            rd(p + 8) != 0x3f800000 || rd(p + 12) != 0x3f800000) continue;
        if (*count == capacity) {
            size_t next = capacity ? capacity * 2 : 16;
            if (next < capacity || next > SIZE_MAX / sizeof(uint64_t)) goto fail;
            uint64_t *q = realloc(*out, next * sizeof(uint64_t));
            if (!q) goto fail;
            *out = q;
            capacity = next;
        }
        (*out)[(*count)++] = (i + 5) * 4;
    }
    return 0;
fail:
    free(*out);
    *out = NULL;
    *count = 0;
    return -1;
}

void release(void *p) { free(p); }
