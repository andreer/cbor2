#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdbool.h>
#include <stdint.h>

// Default readahead buffer size for streaming reads
#define CBOR2_DEFAULT_READ_SIZE 4096

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

    // Read buffer state - points to either readahead[] or external bytes
    const char *read_buf;       // current buffer pointer
    Py_ssize_t read_pos;        // current position in buffer
    Py_ssize_t read_len;        // valid bytes in buffer
    PyObject *read_buf_obj;     // keeps external buffer alive (NULL if using readahead)

    // Readahead buffer for streaming (allocated on first use)
    char *readahead;            // allocated buffer
    Py_ssize_t readahead_size;  // size of allocated buffer (also used as refill size)
} CBORDecoderObject;

extern PyTypeObject CBORDecoderType;

PyObject * CBORDecoder_new(PyTypeObject *, PyObject *, PyObject *);
int CBORDecoder_init(CBORDecoderObject *, PyObject *, PyObject *);
PyObject * CBORDecoder_decode(CBORDecoderObject *);
