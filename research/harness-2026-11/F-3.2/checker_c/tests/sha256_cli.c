/* Test driver for checker_c/sha256.h: prints the SHA-256 of stdin as lowercase hex.
 * With argument "-a N": hashes N bytes of 'a' (the one-million-'a' vector) without reading stdin.
 * Reads stdin in odd-sized chunks so block-boundary handling in sha256_update is exercised. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../sha256.h"

int main(int argc, char **argv)
{
    sha256_ctx c;
    unsigned char out[32], buf[37];
    size_t n;
    int i;
    sha256_init(&c);
    if (argc == 3 && strcmp(argv[1], "-a") == 0) {
        long total = strtol(argv[2], NULL, 10);
        memset(buf, 'a', sizeof buf);
        while (total > 0) {
            size_t k = total > (long)sizeof buf ? sizeof buf : (size_t)total;
            sha256_update(&c, buf, k);
            total -= (long)k;
        }
    } else {
        while ((n = fread(buf, 1, sizeof buf, stdin)) > 0) sha256_update(&c, buf, n);
    }
    sha256_final(&c, out);
    for (i = 0; i < 32; i++) printf("%02x", out[i]);
    printf("\n");
    return 0;
}
