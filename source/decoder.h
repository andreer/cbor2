#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdbool.h>
#include <stdint.h>

// Default readahead buffer size for streaming reads
#define CBOR2_DEFAULT_READ_SIZE 4096

// String key cache configuration
#define STRING_KEY_CACHE_SIZE 256   // Must be power of 2
#define STRING_KEY_MAX_LEN 32       // Only cache strings up to this length

typedef struct {
    PyObject *str;      // Cached Python string (strong reference)
    uint32_t hash;      // Quick hash for comparison
    uint8_t len;        // String length
    char data[STRING_KEY_MAX_LEN];  // Copy of string bytes for comparison
} StringKeyCacheEntry;

typedef struct {
    PyObject_HEAD
    PyObject *read;    // cached read() method of fp
    PyObject *tag_hook;
    PyObject *object_hook;
    PyObject *shareables;
    PyObject *stringref_namespace;
    PyObject *str_errors;
    bool immutable;
    Py_ssize_t shared_index;

    // Readahead buffer for streaming
    char *readahead;            // allocated buffer
    Py_ssize_t readahead_size;  // size of allocated buffer
    Py_ssize_t read_pos;        // current position in buffer
    Py_ssize_t read_len;        // valid bytes in buffer

    // String key cache
    StringKeyCacheEntry string_cache[STRING_KEY_CACHE_SIZE];
} CBORDecoderObject;

extern PyTypeObject CBORDecoderType;

PyObject * CBORDecoder_new(PyTypeObject *, PyObject *, PyObject *);
int CBORDecoder_init(CBORDecoderObject *, PyObject *, PyObject *);
PyObject * CBORDecoder_decode(CBORDecoderObject *);
