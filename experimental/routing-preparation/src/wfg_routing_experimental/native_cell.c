#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <float.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>

/* A bounded exact fast path. All unsupported inputs fall back to Python. */
typedef struct { int64_t mantissa; int exponent; } dyadic;

static int as_dyadic(PyObject *value, dyadic *out) {
    if (PyLong_CheckExact(value)) {
        int overflow = 0;
        long long v = PyLong_AsLongLongAndOverflow(value, &overflow);
        if (overflow || PyErr_Occurred()) { PyErr_Clear(); return 0; }
        out->mantissa = (int64_t)v; out->exponent = 0;
        return 1;
    }
    if (!PyFloat_CheckExact(value)) return 0;
    double v = PyFloat_AS_DOUBLE(value);
    uint64_t bits; memcpy(&bits, &v, sizeof(bits));
    unsigned expbits = (unsigned)((bits >> 52) & 0x7ffu);
    uint64_t frac = bits & UINT64_C(0xfffffffffffff);
    if (expbits == 0x7ffu) return 0; /* NaN or infinity */
    uint64_t m = expbits ? (frac | (UINT64_C(1) << 52)) : frac;
    if (!m) { out->mantissa = 0; out->exponent = 0; return 1; }
    int e = expbits ? ((int)expbits - 1075) : -1074;
    while ((m & 1u) == 0) { m >>= 1; ++e; }
    out->mantissa = (bits >> 63) ? -(int64_t)m : (int64_t)m;
    out->exponent = e;
    return 1;
}

static int scale_dyadic(dyadic a, int exponent, __int128 *out) {
    int shift = a.exponent - exponent;
    if (shift < 0 || shift >= 119) return 0;
    uint64_t m = a.mantissa < 0 ? (uint64_t)(-(a.mantissa + 1)) + 1 : (uint64_t)a.mantissa;
    __uint128_t limit = (((__uint128_t)1 << 119) - 1);
    if ((__uint128_t)m > (limit >> shift)) return 0;
    __int128 n = (__int128)((__uint128_t)m << shift);
    *out = a.mantissa < 0 ? -n : n;
    return 1;
}

static int exact_index(dyadic x, dyadic base, dyadic res, __int128 *idx) {
    int e = x.exponent;
    if (base.exponent < e) e = base.exponent;
    if (res.exponent < e) e = res.exponent;
    __int128 xi, bi, ri;
    if (!scale_dyadic(x,e,&xi) || !scale_dyadic(base,e,&bi) ||
        !scale_dyadic(res,e,&ri) || ri <= 0) return 0;
    __int128 d = xi - bi; /* both magnitudes < 2^119; subtraction fits */
    __int128 q = d / ri;
    if (d < 0 && d % ri) --q; /* C truncates; mathematical floor differs */
    *idx = q;
    return 1;
}

static int positive_i64(PyObject *v, int64_t *out) {
    if (!v || !PyLong_CheckExact(v)) return 0;
    int over = 0; long long n = PyLong_AsLongLongAndOverflow(v, &over);
    if (over || PyErr_Occurred()) { PyErr_Clear(); return 0; }
    if (n <= 0) return 0;
    *out = (int64_t)n; return 1;
}

static PyObject *same_cell(PyObject *self, PyObject *args) {
    PyObject *g,*u,*v;
    if (!PyArg_ParseTuple(args,"OOO",&g,&u,&v)) return NULL;
    if (!PyDict_CheckExact(g) || !PyDict_CheckExact(u) || !PyDict_CheckExact(v)) Py_RETURN_NONE;
    PyObject *values[7] = {PyDict_GetItemString(g,"x0"), PyDict_GetItemString(g,"y0"),
      PyDict_GetItemString(g,"resolution"), PyDict_GetItemString(u,"x"), PyDict_GetItemString(u,"y"),
      PyDict_GetItemString(v,"x"), PyDict_GetItemString(v,"y")};
    if (PyErr_Occurred()) return NULL;
    dyadic d[7]; for (int i=0; i<7; ++i) if (!values[i] || !as_dyadic(values[i], &d[i])) Py_RETURN_NONE;
    PyObject *width_value=PyDict_GetItemString(g,"width"), *height_value=PyDict_GetItemString(g,"height");
    if (PyErr_Occurred()) return NULL;
    int64_t width,height;
    if (!positive_i64(width_value,&width) || !positive_i64(height_value,&height) || height > LLONG_MAX / width) Py_RETURN_NONE;
    __int128 x1,y1,x2,y2;
    if (!exact_index(d[3],d[0],d[2],&x1) || !exact_index(d[4],d[1],d[2],&y1) ||
        !exact_index(d[5],d[0],d[2],&x2) || !exact_index(d[6],d[1],d[2],&y2)) Py_RETURN_NONE;
    if (x1 != x2 || y1 != y2 || x1 < 0 || y1 < 0 || x1 >= width || y1 >= height) Py_RETURN_NONE;
    return PyLong_FromLongLong((long long)(y1 * width + x1));
}

static PyObject *cell_at(PyObject *self, PyObject *args) {
    PyObject *g,*x,*y;
    if (!PyArg_ParseTuple(args,"OOO",&g,&x,&y)) return NULL;
    if (!PyDict_CheckExact(g)) Py_RETURN_NONE;
    PyObject *values[5] = {PyDict_GetItemString(g,"x0"), PyDict_GetItemString(g,"y0"),
                           PyDict_GetItemString(g,"resolution"), x, y};
    if (PyErr_Occurred()) return NULL;
    dyadic d[5]; for (int i=0;i<5;++i) if (!values[i] || !as_dyadic(values[i],&d[i])) Py_RETURN_NONE;
    PyObject *width_value=PyDict_GetItemString(g,"width"), *height_value=PyDict_GetItemString(g,"height");
    if (PyErr_Occurred()) return NULL;
    int64_t width,height;
    if (!positive_i64(width_value,&width) || !positive_i64(height_value,&height) || height > LLONG_MAX / width) Py_RETURN_NONE;
    __int128 col,row;
    if (!exact_index(d[3],d[0],d[2],&col) || !exact_index(d[4],d[1],d[2],&row)) Py_RETURN_NONE;
    if (col < 0 || row < 0 || col >= width || row >= height) Py_RETURN_NONE;
    return PyLong_FromLongLong((long long)(row * width + col));
}

static PyMethodDef methods[] = {{"same_cell",same_cell,METH_VARARGS,"Prove same-cell membership or return None."},
    {"cell_at",cell_at,METH_VARARGS,"Return exact in-bounds cell or None."},{NULL,NULL,0,NULL}};
static struct PyModuleDef module = {PyModuleDef_HEAD_INIT,"wfg_native_cell",NULL,-1,methods};
PyMODINIT_FUNC PyInit_wfg_native_cell(void) {
    double sample[] = {0.0,-0.0,1.0,-1.0,0.5,DBL_MIN,DBL_TRUE_MIN};
    uint64_t expected[] = {UINT64_C(0),UINT64_C(0x8000000000000000),
        UINT64_C(0x3ff0000000000000),UINT64_C(0xbff0000000000000),
        UINT64_C(0x3fe0000000000000),UINT64_C(0x0010000000000000),UINT64_C(1)};
    if (sizeof(double) != 8 || FLT_RADIX != 2 || DBL_MANT_DIG != 53 || DBL_MAX_EXP != 1024) {
        PyErr_SetString(PyExc_ImportError,"binary64 required"); return NULL;
    }
    for (int i=0;i<7;++i) {
        uint64_t actual; memcpy(&actual,&sample[i],sizeof(actual));
        if (actual != expected[i]) {
            PyErr_SetString(PyExc_ImportError,"unsupported double bit layout"); return NULL;
        }
    }
    return PyModule_Create(&module);
}
