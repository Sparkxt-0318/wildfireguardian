/*
 * wfgc_check.c -- independent checker for F-3.2 `.wfgc` certificate bundles (format 1, plus 1.1 COCERT).
 *
 * Written only from CERTIFICATE_SPEC.md and FORMAT.md. C99, integer arithmetic only (int64_t).
 *
 * Usage: wfgc_check <file.wfgc | -> [--expect G=<hex>,A=<hex>,W=<hex>,Q=<hex>]
 * Output: exactly one line.
 *   ACCEPT ROUTE <T>     exit 0
 *   ACCEPT NO_ROUTE <T>  exit 0   (T = H + 1)
 *   Format 2 (BINDING_RULE.md): the BIND section's I digest is recomputed over the instance bytes and must match;
 *   with --expect, G A W Q must match too and the line ends " BOUND <first 16 hex of I>"; without it, " UNBOUND".
 *   A format-1 bundle given --expect is rejected (bind_missing).
 *   REJECT <reason>      exit 1   (certificate / format rejected)
 *   REJECT <reason>      exit 2   (unreadable input, usage error, resource exhaustion)
 *
 * All allocations are held in file-scope pointers so that early exit() never leaks unreachable memory.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <inttypes.h>
#include "sha256.h"

/* Resource limit on node count: per-node adjacency offsets are allocated (counting sort). */
#define MAX_NODES ((int64_t)1 << 27)

typedef struct {
    const int64_t *v; /* v[2*i] = lo_i, v[2*i+1] = hi_i */
    int64_t n;        /* number of intervals */
} IList;

typedef struct {
    int64_t id;
    IList list;
} Rec;

typedef struct {
    int kind; /* 'E' or 'W' */
    int64_t id, a, b;
} Leg;

/* ---------------------------------------------------------------- global state */
static char *g_buf = NULL;
static size_t g_len = 0, g_pos = 0;
static int64_t g_ntok = 0, g_used = 0;

static int64_t *g_pool = NULL;
static int64_t g_pool_cap = 0, g_pool_used = 0;

static int64_t nV, nE, dep, H, origin, s0;
static int64_t *e_tail = NULL, *e_head = NULL, *e_dur = NULL;
static int64_t *waitable = NULL;
static int64_t n_waitable = 0;
static int64_t *forb = NULL; /* pairs (s, j) */
static int64_t n_forb = 0;
static IList *eb = NULL; /* per edge */
static Rec *wb = NULL, *ac = NULL;
static int64_t n_wb = 0, n_ac = 0;

static int claim_route = 0;
static int64_t claim_T = 0;
static Leg *legs = NULL;
static int64_t n_legs = 0;

static int64_t cert_T = 0;
static int64_t n_cert = 0;
static int64_t *cert_s = NULL;
static IList *cert_R = NULL, *cert_A = NULL;
static int64_t *state_rec = NULL; /* size nE+1, index into cert arrays or -1 */

/* COCERT (complement form, format 1.1): parsed NR/NA lists live in cert_R/cert_A until materialised. */
static int cocert = 0;

/* ---------------------------------------------------------------- binding (format 2) */
static int64_t g_version = 0;
static size_t inst_start = 0, inst_end = 0;      /* byte span: 'I' of INSTANCE .. newline after END_INSTANCE */
static unsigned char bind_d[5][32];              /* I G A W Q, as read from BIND */
static unsigned char inst_d[32];                 /* recomputed I */
static int have_expect = 0;
static unsigned char expect_d[4][32];            /* G A W Q from --expect */
static int64_t *co_pool = NULL;
static int64_t *co_s = NULL;
static IList *co_R = NULL, *co_A = NULL;

static int64_t *adj_off = NULL; /* size nV+1 */
static int64_t *adj_edge = NULL; /* size nE */

/* ---------------------------------------------------------------- exits */
static void die(int code, const char *reason)
{
    printf("REJECT %s\n", reason);
    fflush(stdout);
    exit(code);
}

static void rej(const char *reason) { die(1, reason); }

static void *xalloc(int64_t count, size_t elem)
{
    void *p;
    if (count < 0) rej("bad_count");
    if (count == 0) count = 1;
    if ((uint64_t)count > (uint64_t)(SIZE_MAX / elem)) die(2, "out_of_memory");
    p = calloc((size_t)count, elem);
    if (p == NULL) die(2, "out_of_memory");
    return p;
}

/* ---------------------------------------------------------------- input */
static void read_all(FILE *f)
{
    size_t cap = 65536;
    g_buf = (char *)malloc(cap);
    if (g_buf == NULL) die(2, "out_of_memory");
    for (;;) {
        size_t got;
        if (g_len == cap) {
            char *nb;
            if (cap > SIZE_MAX / 2) die(2, "out_of_memory");
            cap *= 2;
            nb = (char *)realloc(g_buf, cap);
            if (nb == NULL) die(2, "out_of_memory");
            g_buf = nb;
        }
        got = fread(g_buf + g_len, 1, cap - g_len, f);
        g_len += got;
        if (got == 0) {
            if (ferror(f)) die(2, "io_error");
            break;
        }
    }
}

static int is_ws(unsigned char c) { return c == ' ' || c == '\t' || c == '\n'; }

/* Validate bytes and count tokens. */
static void scan_tokens(void)
{
    size_t i;
    int in_tok = 0;
    for (i = 0; i < g_len; i++) {
        unsigned char c = (unsigned char)g_buf[i];
        if (is_ws(c)) {
            in_tok = 0;
        } else if (c >= 0x21 && c <= 0x7e) {
            if (!in_tok) {
                if (g_ntok == INT64_MAX) rej("too_many_tokens");
                g_ntok++;
            }
            in_tok = 1;
        } else {
            rej("bad_byte");
        }
    }
}

static int64_t remaining(void) { return g_ntok - g_used; }

static int next_tok(const char **s, size_t *len)
{
    size_t st;
    while (g_pos < g_len && is_ws((unsigned char)g_buf[g_pos])) g_pos++;
    if (g_pos >= g_len) return 0;
    st = g_pos;
    while (g_pos < g_len && !is_ws((unsigned char)g_buf[g_pos])) g_pos++;
    *s = g_buf + st;
    *len = g_pos - st;
    g_used++;
    return 1;
}

static int tok_eq(const char *s, size_t len, const char *kw)
{
    return strlen(kw) == len && memcmp(s, kw, len) == 0;
}

static void expect_kw(const char *kw)
{
    const char *s;
    size_t len;
    if (!next_tok(&s, &len)) rej("unexpected_eof");
    if (!tok_eq(s, len, kw)) rej("bad_keyword");
}

/* Strict decimal: -?(0|[1-9][0-9]*), "-0" rejected, must fit int64. */
static int64_t parse_int(const char *s, size_t len)
{
    size_t i = 0;
    int neg = 0;
    int64_t acc = 0; /* accumulated as a non-positive number */
    if (len == 0) rej("bad_integer");
    if (s[0] == '-') {
        neg = 1;
        i = 1;
    }
    if (i >= len) rej("bad_integer");
    if (s[i] == '0' && (len - i) > 1) rej("bad_integer");
    if (neg && s[i] == '0') rej("bad_integer");
    for (; i < len; i++) {
        int d;
        if (s[i] < '0' || s[i] > '9') rej("bad_integer");
        d = s[i] - '0';
        if (acc < INT64_MIN / 10 || (acc == INT64_MIN / 10 && d > -(INT64_MIN % 10))) rej("bad_integer");
        acc = acc * 10 - d;
    }
    if (!neg) {
        if (acc == INT64_MIN) rej("bad_integer");
        acc = -acc;
    }
    return acc;
}

static int64_t read_int(void)
{
    const char *s;
    size_t len;
    if (!next_tok(&s, &len)) rej("unexpected_eof");
    return parse_int(s, len);
}

/* Read a count k of records each needing at least `per` tokens; reject if impossible. */
static int64_t read_count(int64_t per)
{
    int64_t k = read_int();
    if (k < 0) rej("bad_count");
    if (k > remaining() / per) rej("bad_count");
    return k;
}

static void read_ilist(IList *out)
{
    int64_t m = read_count(2), i;
    int64_t *v;
    if (2 * m > g_pool_cap - g_pool_used) rej("bad_count"); /* cannot happen: pool >= token count */
    v = g_pool + g_pool_used;
    for (i = 0; i < m; i++) {
        int64_t lo = read_int(), hi = read_int();
        if (lo > hi) rej("bad_interval");
        if (i > 0) {
            int64_t ph = v[2 * i - 1];
            /* need ph + 1 < lo, i.e. lo - ph >= 2, without overflow */
            if (ph == INT64_MAX || ph + 1 >= lo) rej("bad_interval");
        }
        v[2 * i] = lo;
        v[2 * i + 1] = hi;
    }
    g_pool_used += 2 * m;
    out->v = v;
    out->n = m;
}

/* ---------------------------------------------------------------- helpers */
static int64_t hd(int64_t s) { return s < nE ? e_head[s] : origin; }

static int in_list(const IList *L, int64_t t)
{
    int64_t lo = 0, hi = L->n - 1;
    while (lo <= hi) {
        int64_t mid = lo + (hi - lo) / 2;
        if (t < L->v[2 * mid]) hi = mid - 1;
        else if (t > L->v[2 * mid + 1]) lo = mid + 1;
        else return 1;
    }
    return 0;
}

static const IList EMPTY = {NULL, 0};

static const IList *find_rec(const Rec *r, int64_t n, int64_t id)
{
    int64_t lo = 0, hi = n - 1;
    while (lo <= hi) {
        int64_t mid = lo + (hi - lo) / 2;
        if (id < r[mid].id) hi = mid - 1;
        else if (id > r[mid].id) lo = mid + 1;
        else return &r[mid].list;
    }
    return &EMPTY;
}

static int is_waitable(int64_t n)
{
    int64_t lo = 0, hi = n_waitable - 1;
    while (lo <= hi) {
        int64_t mid = lo + (hi - lo) / 2;
        if (n < waitable[mid]) hi = mid - 1;
        else if (n > waitable[mid]) lo = mid + 1;
        else return 1;
    }
    return 0;
}

static int is_forbidden(int64_t s, int64_t j)
{
    int64_t lo = 0, hi = n_forb - 1;
    while (lo <= hi) {
        int64_t mid = lo + (hi - lo) / 2;
        int64_t ms = forb[2 * mid], mj = forb[2 * mid + 1];
        if (s < ms || (s == ms && j < mj)) hi = mid - 1;
        else if (s > ms || (s == ms && j > mj)) lo = mid + 1;
        else return 1;
    }
    return 0;
}

static const IList *A_of(int64_t s)
{
    int64_t r = state_rec[s];
    return r < 0 ? &EMPTY : &cert_A[r];
}

/* ---------------------------------------------------------------- parsing */
static void read_node_records(Rec **out, int64_t *count)
{
    int64_t k = read_count(2), i;
    Rec *r = (Rec *)xalloc(k, sizeof(Rec));
    *out = r;
    for (i = 0; i < k; i++) {
        int64_t n = read_int();
        if (n < 0 || n >= nV) rej("bad_range");
        if (i > 0 && n <= r[i - 1].id) rej("bad_order");
        r[i].id = n;
        read_ilist(&r[i].list);
    }
    *count = k;
}

/* BIND section (format 2): END_INSTANCE must be followed directly by a newline; the instance digest covers the bytes
 * from the 'I' of INSTANCE through that newline. Then BIND, five records "<field> w1 .. w8" in the fixed order
 * I G A W Q (words in [0, 2^32 - 1], big-endian), END_BIND. */
static void read_bind(void)
{
    static const char *fields[5] = {"I", "G", "A", "W", "Q"};
    int f, w;
    sha256_ctx c;
    if (g_pos >= g_len || g_buf[g_pos] != '\n') rej("bind_layout");
    inst_end = g_pos + 1;
    sha256_init(&c);
    sha256_update(&c, (const unsigned char *)g_buf + inst_start, inst_end - inst_start);
    sha256_final(&c, inst_d);
    expect_kw("BIND");
    for (f = 0; f < 5; f++) {
        expect_kw(fields[f]);
        for (w = 0; w < 8; w++) {
            int64_t v = read_int();
            if (v < 0 || v > (int64_t)0xffffffff) rej("bind_word_range");
            bind_d[f][4 * w] = (unsigned char)(v >> 24);
            bind_d[f][4 * w + 1] = (unsigned char)(v >> 16);
            bind_d[f][4 * w + 2] = (unsigned char)(v >> 8);
            bind_d[f][4 * w + 3] = (unsigned char)v;
        }
    }
    expect_kw("END_BIND");
    if (memcmp(bind_d[0], inst_d, 32) != 0) rej("bind_instance_digest");
}

static int hexval(char ch)
{
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    return -1;
}

/* --expect G=<64 hex>,A=<64 hex>,W=<64 hex>,Q=<64 hex>, exactly this order, lowercase hex. */
static void parse_expect(const char *arg)
{
    static const char names[4] = {'G', 'A', 'W', 'Q'};
    size_t pos = 0;
    int f, i;
    if (strlen(arg) != 4 * 67 - 1) die(2, "bad_expect");
    for (f = 0; f < 4; f++) {
        if (arg[pos] != names[f] || arg[pos + 1] != '=') die(2, "bad_expect");
        pos += 2;
        for (i = 0; i < 32; i++) {
            int hi = hexval(arg[pos + 2 * i]), lo = hexval(arg[pos + 2 * i + 1]);
            if (hi < 0 || lo < 0) die(2, "bad_expect");
            expect_d[f][i] = (unsigned char)(hi * 16 + lo);
        }
        pos += 64;
        if (f < 3) {
            if (arg[pos] != ',') die(2, "bad_expect");
            pos++;
        }
    }
    have_expect = 1;
}

static void check_bind_expect(void)
{
    static const char *reason[4] = {"bind_G", "bind_A", "bind_W", "bind_Q"};
    int f;
    if (!have_expect) return;
    if (g_version != 2) rej("bind_missing");
    for (f = 0; f < 4; f++)
        if (memcmp(bind_d[f + 1], expect_d[f], 32) != 0) rej(reason[f]);
}

static void parse(void)
{
    int64_t i, k, prev;
    const char *s;
    size_t len;

    expect_kw("WFGC");
    g_version = read_int();
    if (g_version != 1 && g_version != 2) rej("bad_version");
    expect_kw("INSTANCE");
    inst_start = g_pos - 8;                      /* next_tok left g_pos just after "INSTANCE" (8 bytes) */
    expect_kw("V");
    nV = read_int();
    expect_kw("E");
    nE = read_int();
    if (nV < 1 || nE < 0) rej("bad_range");
    if (nV > MAX_NODES) die(2, "resource_limit");
    if (nE > remaining() / 3) rej("bad_count");
    expect_kw("DEP");
    dep = read_int();
    expect_kw("HOR");
    H = read_int();
    expect_kw("ORIGIN");
    origin = read_int();
    expect_kw("START");
    s0 = read_int();
    if (dep < 0 || dep > H) rej("bad_dep_horizon");
    if (H == INT64_MAX) rej("horizon_overflow");
    if (origin < 0 || origin >= nV) rej("bad_range");
    if (s0 < 0 || s0 > nE) rej("bad_range");

    expect_kw("EDGES");
    e_tail = (int64_t *)xalloc(nE, sizeof(int64_t));
    e_head = (int64_t *)xalloc(nE, sizeof(int64_t));
    e_dur = (int64_t *)xalloc(nE, sizeof(int64_t));
    for (i = 0; i < nE; i++) {
        e_tail[i] = read_int();
        e_head[i] = read_int();
        e_dur[i] = read_int();
        if (e_tail[i] < 0 || e_tail[i] >= nV || e_head[i] < 0 || e_head[i] >= nV) rej("bad_range");
        if (e_dur[i] < 1) rej("bad_duration");
    }
    if (s0 < nE && e_head[s0] != origin) rej("start_head_mismatch");

    expect_kw("WAITABLE");
    n_waitable = read_count(1);
    waitable = (int64_t *)xalloc(n_waitable, sizeof(int64_t));
    for (i = 0; i < n_waitable; i++) {
        waitable[i] = read_int();
        if (waitable[i] < 0 || waitable[i] >= nV) rej("bad_range");
        if (i > 0 && waitable[i] <= waitable[i - 1]) rej("bad_order");
    }

    expect_kw("FORBID");
    n_forb = read_count(2);
    forb = (int64_t *)xalloc(2 * n_forb, sizeof(int64_t));
    for (i = 0; i < n_forb; i++) {
        int64_t fs = read_int(), fj = read_int();
        if (fs < 0 || fs > nE || fj < 0 || fj >= nE) rej("bad_range");
        if (i > 0) {
            int64_t ps = forb[2 * i - 2], pj = forb[2 * i - 1];
            if (fs < ps || (fs == ps && fj <= pj)) rej("bad_order");
        }
        forb[2 * i] = fs;
        forb[2 * i + 1] = fj;
    }

    expect_kw("EB");
    k = read_count(2);
    eb = (IList *)xalloc(nE, sizeof(IList));
    prev = -1;
    for (i = 0; i < k; i++) {
        int64_t j = read_int();
        if (j < 0 || j >= nE) rej("bad_range");
        if (j <= prev) rej("bad_order");
        prev = j;
        read_ilist(&eb[j]);
    }

    expect_kw("WB");
    read_node_records(&wb, &n_wb);
    expect_kw("AC");
    read_node_records(&ac, &n_ac);
    expect_kw("END_INSTANCE");
    if (g_version == 2) read_bind();

    expect_kw("CLAIM");
    if (!next_tok(&s, &len)) rej("unexpected_eof");
    if (tok_eq(s, len, "ROUTE")) {
        claim_route = 1;
        claim_T = read_int();
    } else if (tok_eq(s, len, "NO_ROUTE")) {
        claim_route = 0;
    } else {
        rej("bad_keyword");
    }

    expect_kw("WITNESS");
    n_legs = read_count(4);
    legs = (Leg *)xalloc(n_legs, sizeof(Leg));
    for (i = 0; i < n_legs; i++) {
        if (!next_tok(&s, &len)) rej("unexpected_eof");
        if (tok_eq(s, len, "E")) legs[i].kind = 'E';
        else if (tok_eq(s, len, "W")) legs[i].kind = 'W';
        else rej("bad_keyword");
        legs[i].id = read_int();
        legs[i].a = read_int();
        legs[i].b = read_int();
    }

    if (!next_tok(&s, &len)) rej("unexpected_eof");
    if (tok_eq(s, len, "CERT")) cocert = 0;
    else if (tok_eq(s, len, "COCERT")) cocert = 1;
    else rej("bad_keyword");
    cert_T = read_int();
    n_cert = read_count(3);
    cert_s = (int64_t *)xalloc(n_cert, sizeof(int64_t));
    cert_R = (IList *)xalloc(n_cert, sizeof(IList));
    cert_A = (IList *)xalloc(n_cert, sizeof(IList));
    for (i = 0; i < n_cert; i++) {
        int64_t st = read_int();
        if (st < 0 || st > nE) rej("bad_range");
        if (i > 0 && st <= cert_s[i - 1]) rej("bad_order");
        cert_s[i] = st;
        read_ilist(&cert_R[i]);
        read_ilist(&cert_A[i]);
    }
    expect_kw("END");
    if (next_tok(&s, &len)) rej("trailing_tokens");
}

/* ---------------------------------------------------------------- checks */
static void check_claim(void)
{
    if (claim_route) {
        if (claim_T < dep || claim_T > H) rej("claim_threshold");
        if (cert_T != claim_T) rej("cert_threshold_mismatch");
    } else {
        if (n_legs != 0) rej("no_route_witness");
        if (cert_T != H + 1) rej("cert_threshold_mismatch");
    }
    /* spec: dep <= T <= H+1 (implied by the above, kept explicit) */
    if (cert_T < dep || cert_T > H + 1) rej("cert_threshold");
}

static void build_index(void)
{
    int64_t i;
    int64_t *fill;
    state_rec = (int64_t *)xalloc(nE + 1, sizeof(int64_t));
    for (i = 0; i <= nE; i++) state_rec[i] = -1;
    for (i = 0; i < n_cert; i++) state_rec[cert_s[i]] = i;

    /* adjacency by counting sort on tail */
    adj_off = (int64_t *)xalloc(nV + 1, sizeof(int64_t));
    adj_edge = (int64_t *)xalloc(nE, sizeof(int64_t));
    for (i = 0; i < nE; i++) adj_off[e_tail[i] + 1]++;
    for (i = 0; i < nV; i++) adj_off[i + 1] += adj_off[i];
    fill = (int64_t *)xalloc(nV, sizeof(int64_t));
    for (i = 0; i < nV; i++) fill[i] = adj_off[i];
    for (i = 0; i < nE; i++) adj_edge[fill[e_tail[i]]++] = i;
    free(fill);
}

/* C0: bounds in [dep, H] and A subset of R (list well-formedness was enforced while parsing). */
static void check_c0(void)
{
    int64_t r;
    for (r = 0; r < n_cert; r++) {
        const IList *R = &cert_R[r], *A = &cert_A[r];
        int64_t ia, ir = 0;
        if (R->n > 0 && (R->v[0] < dep || R->v[2 * R->n - 1] > H)) rej("c0_bounds");
        if (A->n > 0 && (A->v[0] < dep || A->v[2 * A->n - 1] > H)) rej("c0_bounds");
        for (ia = 0; ia < A->n; ia++) {
            int64_t lo = A->v[2 * ia], hi = A->v[2 * ia + 1];
            while (ir < R->n && R->v[2 * ir + 1] < lo) ir++;
            if (ir >= R->n || R->v[2 * ir] > lo || R->v[2 * ir + 1] < hi) rej("c0_a_not_subset_r");
        }
    }
}

static void check_c1(void)
{
    if (dep < cert_T && !in_list(A_of(s0), dep)) rej("c1_init");
}

static int64_t lim_T(void)
{
    /* min(H, T-1); T >= dep >= 0 so T-1 does not overflow */
    int64_t t1 = cert_T - 1;
    return t1 < H ? t1 : H;
}

/* Write [dep, lim] \ N into out (N already validated inside [dep, lim]); returns interval count. */
static int64_t complement(const IList *N, int64_t lim, int64_t *out)
{
    int64_t i, k = 0, cur = dep; /* cur = first second not yet covered/emitted; cur <= lim + 1 */
    if (dep > lim) return 0;
    for (i = 0; i < N->n; i++) {
        int64_t lo = N->v[2 * i], hi = N->v[2 * i + 1];
        if (lo > cur) {
            out[2 * k] = cur;
            out[2 * k + 1] = lo - 1;
            k++;
        }
        cur = hi + 1; /* hi <= lim <= H < INT64_MAX: no overflow */
    }
    if (cur <= lim) {
        out[2 * k] = cur;
        out[2 * k + 1] = lim;
        k++;
    }
    return k;
}

static void within(const IList *N, int64_t lim)
{
    if (N->n > 0 && (dep > lim || N->v[0] < dep || N->v[2 * N->n - 1] > lim)) rej("cocert_bounds");
}

/* COCERT: validate NR, NA in [dep, lim], NR subset NA, then materialise R, A for every state 0..nE. */
static void materialise_cocert(void)
{
    int64_t lim = lim_T(), r, st, need = 0, used = 0, nst = nE + 1;
    for (r = 0; r < n_cert; r++) {
        const IList *NR = &cert_R[r], *NA = &cert_A[r];
        int64_t ir, ia = 0;
        within(NR, lim);
        within(NA, lim);
        for (ir = 0; ir < NR->n; ir++) {
            int64_t lo = NR->v[2 * ir], hi = NR->v[2 * ir + 1];
            while (ia < NA->n && NA->v[2 * ia + 1] < lo) ia++;
            if (ia >= NA->n || NA->v[2 * ia] > lo || NA->v[2 * ia + 1] < hi) rej("cocert_nr_not_subset_na");
        }
        /* complement of m intervals has at most m+1 intervals, 2 numbers each */
        need += 2 * (NR->n + 1) + 2 * (NA->n + 1);
    }
    need += 4 * (nst - n_cert); /* unlisted: one interval each for R and A (bounded: nE <= tokens) */
    co_pool = (int64_t *)xalloc(need, sizeof(int64_t));
    co_s = (int64_t *)xalloc(nst, sizeof(int64_t));
    co_R = (IList *)xalloc(nst, sizeof(IList));
    co_A = (IList *)xalloc(nst, sizeof(IList));
    r = 0;
    for (st = 0; st < nst; st++) {
        static const IList none = {NULL, 0};
        const IList *NR = &none, *NA = &none;
        if (r < n_cert && cert_s[r] == st) {
            NR = &cert_R[r];
            NA = &cert_A[r];
            r++;
        }
        co_s[st] = st;
        co_R[st].v = co_pool + used;
        co_R[st].n = complement(NR, lim, co_pool + used);
        used += 2 * co_R[st].n;
        co_A[st].v = co_pool + used;
        co_A[st].n = complement(NA, lim, co_pool + used);
        used += 2 * co_A[st].n;
    }
    /* swap in the materialised certificate; old arrays stay reachable via globals below */
    free(cert_s);
    free(cert_R);
    free(cert_A);
    cert_s = co_s;
    cert_R = co_R;
    cert_A = co_A;
    co_s = NULL;
    co_R = co_A = NULL;
    n_cert = nst;
}

/* C2: { t + D_j : t in R_s \ EB_j, t + D_j <= lim } subset of A_j, by linear merge. */
static void check_c2(void)
{
    int64_t lim = lim_T(), r, x;
    for (r = 0; r < n_cert; r++) {
        int64_t s = cert_s[r];
        const IList *R = &cert_R[r];
        int64_t u = hd(s);
        if (R->n == 0) continue;
        for (x = adj_off[u]; x < adj_off[u + 1]; x++) {
            int64_t j = adj_edge[x];
            int64_t d = e_dur[j];
            int64_t maxt, ir, ie = 0, ia = 0;
            const IList *EBj = &eb[j], *Aj = A_of(j);
            if (is_forbidden(s, j)) continue;
            /* lim >= -1 and d >= 1, so lim - d >= INT64_MIN: no overflow */
            maxt = lim - d;
            for (ir = 0; ir < R->n; ir++) {
                int64_t lo = R->v[2 * ir], hi = R->v[2 * ir + 1];
                int64_t cur, hi2 = hi < maxt ? hi : maxt;
                if (lo > hi2) break; /* later intervals start even later */
                cur = lo;
                for (;;) {
                    int64_t seg_end;
                    while (ie < EBj->n && EBj->v[2 * ie + 1] < cur) ie++;
                    if (ie < EBj->n && EBj->v[2 * ie] <= cur) {
                        /* cur is blocked; skip past this EB interval */
                        if (EBj->v[2 * ie + 1] >= hi2) break;
                        cur = EBj->v[2 * ie + 1] + 1;
                        continue;
                    }
                    seg_end = hi2;
                    if (ie < EBj->n && EBj->v[2 * ie] - 1 < seg_end) seg_end = EBj->v[2 * ie] - 1;
                    {
                        /* piece [cur, seg_end] shifted by d; seg_end + d <= lim, no overflow */
                        int64_t plo = cur + d, phi = seg_end + d;
                        while (ia < Aj->n && Aj->v[2 * ia + 1] < plo) ia++;
                        if (ia >= Aj->n || Aj->v[2 * ia] > plo || Aj->v[2 * ia + 1] < phi) rej("c2_edge_closure");
                    }
                    if (seg_end >= hi2) break;
                    cur = seg_end + 1;
                }
            }
        }
    }
}

/* C3: every maximal interval [lo,hi] of R_s with hi + 1 <= lim has hi in WB_hd(s), for waitable hd(s). */
static void check_c3(void)
{
    int64_t lim = lim_T(), r, ir;
    for (r = 0; r < n_cert; r++) {
        int64_t u = hd(cert_s[r]);
        const IList *R = &cert_R[r], *W;
        if (!is_waitable(u)) continue;
        W = find_rec(wb, n_wb, u);
        for (ir = 0; ir < R->n; ir++) {
            int64_t hi = R->v[2 * ir + 1];
            if (hi < lim && !in_list(W, hi)) rej("c3_wait_closure");
        }
    }
}

/* C4: A_s ∩ AC_hd(s) ∩ (-inf, T-1] = ∅. */
static void check_c4(void)
{
    int64_t r;
    int64_t tmax = cert_T - 1;
    for (r = 0; r < n_cert; r++) {
        const IList *A = &cert_A[r], *C = find_rec(ac, n_ac, hd(cert_s[r]));
        int64_t ia = 0, ic = 0;
        while (ia < A->n && ic < C->n) {
            int64_t alo = A->v[2 * ia], ahi = A->v[2 * ia + 1];
            int64_t clo = C->v[2 * ic], chi = C->v[2 * ic + 1];
            int64_t lo = alo > clo ? alo : clo;
            int64_t hi = ahi < chi ? ahi : chi;
            if (lo <= hi && lo <= tmax) rej("c4_goal_in_certificate");
            if (ahi < chi) ia++;
            else ic++;
        }
    }
}

static void check_witness(void)
{
    int64_t i, st = s0, t = dep;
    int admitted = 1;
    if (!claim_route) return;
    for (i = 0; i < n_legs; i++) {
        const Leg *L = &legs[i];
        if (L->a != t) rej("witness_not_contiguous");
        if (L->kind == 'E') {
            int64_t j = L->id;
            if (j < 0 || j >= nE) rej("witness_bad_edge");
            if (e_tail[j] != hd(st)) rej("witness_edge_not_incident");
            if (is_forbidden(st, j)) rej("witness_forbidden_turn");
            if (in_list(&eb[j], L->a)) rej("witness_departure_blocked");
            if (e_dur[j] > INT64_MAX - L->a || L->b != L->a + e_dur[j]) rej("witness_duration");
            if (L->b > H) rej("witness_beyond_horizon");
            st = j;
            admitted = 1;
        } else {
            int64_t n = L->id;
            if (n < 0 || n >= nV) rej("witness_bad_node");
            if (n != hd(st)) rej("witness_wait_wrong_node");
            if (!is_waitable(n)) rej("witness_wait_not_waitable");
            if (in_list(find_rec(wb, n_wb, n), L->a)) rej("witness_wait_blocked");
            if (L->a == INT64_MAX || L->b != L->a + 1) rej("witness_duration");
            if (L->b > H) rej("witness_beyond_horizon");
            admitted = 0;
        }
        t = L->b;
    }
    if (!admitted) rej("witness_final_not_admitted");
    if (t != claim_T) rej("witness_arrival_not_T");
    if (!in_list(find_rec(ac, n_ac, hd(st)), t)) rej("witness_final_not_accepted");
}

int main(int argc, char **argv)
{
    FILE *f;
    if (argc == 4 && strcmp(argv[2], "--expect") == 0) parse_expect(argv[3]);
    else if (argc != 2) die(2, "usage");
    if (strcmp(argv[1], "-") == 0) {
        f = stdin;
    } else {
        f = fopen(argv[1], "rb");
        if (f == NULL) die(2, "io_error");
    }
    read_all(f);
    if (f != stdin) fclose(f);

    scan_tokens();
    if (g_ntok == 0) rej("empty_input");
    g_pool_cap = g_ntok;
    g_pool = (int64_t *)xalloc(g_pool_cap, sizeof(int64_t));

    parse();
    check_bind_expect();
    check_claim();
    if (cocert) materialise_cocert();
    build_index();
    check_c0();
    check_c1();
    check_c2();
    check_c3();
    check_c4();
    check_witness();

    printf("ACCEPT %s %" PRId64, claim_route ? "ROUTE" : "NO_ROUTE", cert_T);
    if (g_version == 2) {
        if (have_expect) {
            int i;
            printf(" BOUND ");
            for (i = 0; i < 8; i++) printf("%02x", inst_d[i]);
        } else {
            printf(" UNBOUND");
        }
    }
    printf("\n");
    return 0;
}
