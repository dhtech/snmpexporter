/*
 * MIB resolver for snmpcollector
 */

#include <stdio.h>
#include <ctype.h>
#include <net-snmp/net-snmp-config.h>
#include <net-snmp/mib_api.h>
#include <net-snmp/library/default_store.h>

#include <Python.h>


#define MAX_OUTPUT 1024


struct module_state {
      PyObject *error;
};

static PyObject *resolve(PyObject *self, PyObject *args) {
  oid name[MAX_OID_LEN];
  size_t name_length = MAX_OID_LEN;
  const char *input;
  char output[MAX_OUTPUT];
  struct tree *tp;
  PyObject *enum_map;

  if (!PyArg_ParseTuple(args, "s", &input)) {
    return NULL;
  }

  if (read_objid(input, name, &name_length) != 1) {
    return Py_None;
  }

  /* Resolve the OID */
  snprint_objid(output, sizeof(output), name, name_length);

  /* Resolve enum values if we have any */
  enum_map = PyDict_New();
  tp = get_tree(name, name_length, get_tree_head());
  if (tp->enums) {
    struct enum_list *ep = tp->enums;
    while (ep) {
      PyObject *key = PyUnicode_FromFormat("%d", ep->value);
      PyObject *val = PyUnicode_FromString(ep->label);
      PyDict_SetItem(enum_map, key, val);
      Py_DECREF(key);
      Py_DECREF(val);
      ep = ep->next;
    }
  }

  PyObject* ret = Py_BuildValue("sO", output, enum_map);
  Py_DECREF(output);
  Py_DECREF(enum_map);
  return ret;
}

static int module_traverse(PyObject *m, visitproc visit, void *arg) {
  Py_VISIT(((struct module_state*)PyModule_GetState(m))->error);
  return 0;
}

static int module_clear(PyObject *m) {
  Py_CLEAR(((struct module_state*)PyModule_GetState(m))->error);
  return 0;
}

static PyMethodDef module_funcs[] = {
  { "resolve", resolve, METH_VARARGS, "Try to resolve a given OID." },
  { NULL, NULL, 0, NULL }
};

static struct PyModuleDef moduledef = {
  PyModuleDef_HEAD_INIT,
  "mibresolver",
  "MIB resolver utilities",
  sizeof(struct module_state),
  module_funcs,
  NULL,
  module_traverse,
  module_clear,
  NULL
};

PyMODINIT_FUNC PyInit_mibresolver(void) {
  PyObject *module = PyModule_Create(&moduledef);

  if (module == NULL)
    return NULL;

  struct module_state *st = (struct module_state*)PyModule_GetState(module);

  st->error = PyErr_NewException("mibresolver.Error", NULL, NULL);
  if (st->error == NULL) {
    Py_DECREF(module);
    return NULL;
  }

  /* Turn off noisy MIB debug logging */
  netsnmp_register_loghandler(NETSNMP_LOGHANDLER_NONE, 0);

  /* Print indexes in integer format and not ASCII converted */
  netsnmp_ds_set_boolean(
      NETSNMP_DS_LIBRARY_ID, NETSNMP_DS_LIB_DONT_BREAKDOWN_OIDS, 1);

  init_snmp("snmpapp");
  return module;
}
