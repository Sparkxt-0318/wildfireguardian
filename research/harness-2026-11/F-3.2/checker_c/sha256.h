/* SHA-256 per FIPS 180-4 (sections 4.1.2, 4.2.2, 5.1.1, 5.3.3, 6.2). Written for the F-3.2 C checker
 * (BINDING_RULE R2); shares no code with the Python side. C99, fixed-width types, no dynamic memory.
 * Streaming interface: sha256_init / sha256_update / sha256_final. */
#ifndef WFGC_SHA256_H
#define WFGC_SHA256_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t h[8];
    uint64_t nbytes;          /* total message length in bytes so far */
    unsigned char buf[64];
    size_t nbuf;              /* bytes currently in buf, 0..63 */
} sha256_ctx;

static const uint32_t SHA256_K[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
    0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u, 0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
    0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu, 0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u, 0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
    0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u, 0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
    0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u, 0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u
};

static uint32_t sha256_rotr(uint32_t x, unsigned n) { return (x >> n) | (x << (32u - n)); }

static void sha256_init(sha256_ctx *c)
{
    static const uint32_t H0[8] = {0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
                                   0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u};
    int i;
    for (i = 0; i < 8; i++) c->h[i] = H0[i];
    c->nbytes = 0;
    c->nbuf = 0;
}

static void sha256_block(sha256_ctx *c, const unsigned char *p)
{
    uint32_t w[64], a, b, cc, d, e, f, g, h, t1, t2;
    int t;
    for (t = 0; t < 16; t++)
        w[t] = ((uint32_t)p[4 * t] << 24) | ((uint32_t)p[4 * t + 1] << 16) |
               ((uint32_t)p[4 * t + 2] << 8) | (uint32_t)p[4 * t + 3];
    for (t = 16; t < 64; t++) {
        uint32_t s0 = sha256_rotr(w[t - 15], 7) ^ sha256_rotr(w[t - 15], 18) ^ (w[t - 15] >> 3);
        uint32_t s1 = sha256_rotr(w[t - 2], 17) ^ sha256_rotr(w[t - 2], 19) ^ (w[t - 2] >> 10);
        w[t] = s1 + w[t - 7] + s0 + w[t - 16];
    }
    a = c->h[0]; b = c->h[1]; cc = c->h[2]; d = c->h[3];
    e = c->h[4]; f = c->h[5]; g = c->h[6]; h = c->h[7];
    for (t = 0; t < 64; t++) {
        uint32_t S1 = sha256_rotr(e, 6) ^ sha256_rotr(e, 11) ^ sha256_rotr(e, 25);
        uint32_t ch = (e & f) ^ (~e & g);
        uint32_t S0 = sha256_rotr(a, 2) ^ sha256_rotr(a, 13) ^ sha256_rotr(a, 22);
        uint32_t maj = (a & b) ^ (a & cc) ^ (b & cc);
        t1 = h + S1 + ch + SHA256_K[t] + w[t];
        t2 = S0 + maj;
        h = g; g = f; f = e; e = d + t1;
        d = cc; cc = b; b = a; a = t1 + t2;
    }
    c->h[0] += a; c->h[1] += b; c->h[2] += cc; c->h[3] += d;
    c->h[4] += e; c->h[5] += f; c->h[6] += g; c->h[7] += h;
}

static void sha256_update(sha256_ctx *c, const unsigned char *p, size_t n)
{
    c->nbytes += (uint64_t)n;
    while (n > 0) {
        size_t take = 64 - c->nbuf;
        if (take > n) take = n;
        {
            size_t i;
            for (i = 0; i < take; i++) c->buf[c->nbuf + i] = p[i];
        }
        c->nbuf += take; p += take; n -= take;
        if (c->nbuf == 64) {
            sha256_block(c, c->buf);
            c->nbuf = 0;
        }
    }
}

/* out: 32 bytes, big-endian words. */
static void sha256_final(sha256_ctx *c, unsigned char out[32])
{
    uint64_t bits = c->nbytes * 8u;
    int i;
    c->buf[c->nbuf++] = 0x80;
    if (c->nbuf > 56) {                     /* no room for the 8-byte length: pad this block, start another */
        while (c->nbuf < 64) c->buf[c->nbuf++] = 0;
        sha256_block(c, c->buf);
        c->nbuf = 0;
    }
    while (c->nbuf < 56) c->buf[c->nbuf++] = 0;
    for (i = 0; i < 8; i++) c->buf[56 + i] = (unsigned char)(bits >> (56 - 8 * i));
    sha256_block(c, c->buf);
    for (i = 0; i < 8; i++) {
        out[4 * i] = (unsigned char)(c->h[i] >> 24);
        out[4 * i + 1] = (unsigned char)(c->h[i] >> 16);
        out[4 * i + 2] = (unsigned char)(c->h[i] >> 8);
        out[4 * i + 3] = (unsigned char)(c->h[i]);
    }
}

#endif
