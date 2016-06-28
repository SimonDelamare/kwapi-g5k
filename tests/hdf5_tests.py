import os
import kwapi.plugins.hdf5.app as app
import unittest
import tempfile
import time
import json
import socket
import shutil
import errno


def stringtojson(rv):
    json_rv = {}
    try:
        json_rv = json.loads(rv.data)
    except ValueError as error:
        print "Can't parse JSON %s" % error
        print "%s" % rv.data
        raise error
    return json_rv


class HDF5TestCase(unittest.TestCase):
    def setUp(self):
        self.log_file_fd, app.cfg.CONF.log_file = tempfile.mkstemp()
        app.cfg.CONF.hdf5_dir = tempfile.mkdtemp()
        self.endpoint_fd, probes_endpoint = tempfile.mkstemp()
        app.cfg.CONF.probes_endpoint = ["ipc://" + probes_endpoint]
        # HDF5 dates
        app.cfg.CONF.start_date = "2014/11/01"
        app.cfg.CONF.split_days = 0
        app.cfg.CONF.split_weeks = 0
        app.cfg.CONF.split_months = 1
        my_app = app.make_app()
        self.storePower = app.storePower
        self.storeNetworkIn = app.storeNetworkIn
        self.storeNetworkOut = app.storeNetworkOut
        self.app = my_app.test_client()
        self.site = socket.getfqdn().split('.')
        self.site = self.site[1] if len(self.site) >= 2 else self.site[0]

    def tearDown(self):
        os.close(self.log_file_fd)
        os.unlink(app.cfg.CONF.log_file)
        os.close(self.endpoint_fd)
        os.unlink(app.cfg.CONF.probes_endpoint[0][6:])
        # Delete temporary HDF5 files
        try:
            shutil.rmtree(app.cfg.CONF.hdf5_dir)
        except OSError as e:
            # Reraise unless ENOENT: No such file or directory
            # (ok if directory has already been deleted)
            if e.errno != errno.ENOENT:
                raise
        # Kill collector threads
        try:
            app.signal_handler(None, None)
        except SystemExit:
            print "Exit correctly"
        self.storePower = None
        self.storeNetworkIn = None
        self.storeNetworkOut = None

    def test_empty_root(self):
        rv = self.app.get("/", headers={"Accept": "grid5000"})
        self.assertEqual({"items": [{}, {}, {}]}, stringtojson(rv))

    def test_empty_metric(self):
        rv = self.app.get('/power/', headers={"Accept": "grid5000"})
        self.assertEqual({}, stringtojson(rv))

    def test_empty_metric_timeseries(self):
        rv = self.app.get('/power/timeseries/', headers={"Accept": "grid5000"})
        a = {u'items': [],
             u'links': [
                 {u'href': u'/sid/%s' % self.site,
                  u'rel': u'self',
                  u'type': u'application/vnd.fr.grid5000.api.Collection+json;level=1'},
                 {u'href': u'/sid/sites/%s' % self.site,
                  u'rel': u'parent',
                  u'type': u'application/vnd.fr.grid5000.api.Metric+json;level=1'}],
             u'offset': 0,
             u'total': 0}
        self.assertEqual(a, stringtojson(rv))

if __name__ == '__main__':
    unittest.main()
