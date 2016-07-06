# coding=utf-8
import os
import kwapi.plugins.live.app as app
import unittest
import tempfile
import time
import socket
import shutil
import errno


class HDF5TestCase(unittest.TestCase):
    def add_value(self, probe, probes_names, data_type, timestamp, metrics,
                  params):
        return self.live.update_probe(probe, probes_names, data_type,
                                      timestamp, metrics, params)

    def setUp(self):
        self.log_file_fd, app.cfg.CONF.log_file = tempfile.mkstemp()
        app.cfg.CONF.hdf5_dir = tempfile.mkdtemp()
        self.endpoint_fd, probes_endpoint = tempfile.mkstemp()
        app.cfg.CONF.probes_endpoint = ["ipc://" + probes_endpoint]
        app.cfg.CONF.rrd_port = 8080
        self.site = socket.getfqdn().split('.')
        self.site = self.site[1] if len(self.site) >= 2 else self.site[0]
        app.cfg.CONF.g5k_sites = "['%s',]" % self.site
        # PNG and RRD directories
        app.cfg.CONF.png_dir = tempfile.mkdtemp()
        app.cfg.CONF.rrd_dir = tempfile.mkdtemp()
        # Other Live parameters
        app.cfg.CONF.currency = "€"
        app.cfg.CONF.kwh_price = 0.04
        app.cfg.CONF.hue = 100
        app.cfg.CONF.max_metrics = 400
        app.cfg.CONF.refresh_interval = 5
        app.cfg.CONF.size = 160
        app.cfg.CONF.verbose = True

        self.live = app.live
        my_app = app.make_app()
        self.app = my_app.test_client()

    def add_data(self, t=int(time.time())):
        probe = "%s.%s" % (self.site, "bar-1")
        pdu = "%s.%s.%d" % (self.site, "pdu", 1)
        switch = "%s.%s.%d-%d" % (self.site, "switch", 1, 1)
        self.add_value(pdu, [probe], 'power', t, 1, {'type': "power", 'unit': "KW"})
        self.add_value(switch, [probe], 'network_in', t, 1,
                       {'type': "network_in", 'unit': "B"})
        self.add_value(switch, [probe], 'network_out', t, 1,
                       {'type': "network_out", 'unit': "B"})

    def tearDown(self):
        # Kill collector threads
        try:
            app.signal_handler(None, None)
        except SystemExit:
            print "Exit correctly"
        except Exception as e:
            print "Error when exiting app: %s" % e
        try:
            self.h5c.clear_probes(self.h5c)
        except Exception as e:
            print "Error when clear probe set: %s" % e
        try:
            self.storePower = None
            self.storeNetworkIn = None
            self.storeNetworkOut = None
        except Exception as e:
            print "Error when removing stores: %s" % e
        try:
            os.close(self.log_file_fd)
            os.unlink(app.cfg.CONF.log_file)
            os.close(self.endpoint_fd)
            os.unlink(app.cfg.CONF.probes_endpoint[0][6:])
        except Exception as e:
            print "Error when cleaning tmp files: %s" % e
        # Delete temporary HDF5 files
        try:
            shutil.rmtree(app.cfg.CONF.hdf5_dir)
            shutil.rmtree(app.cfg.CONF.rrd_dir)
            shutil.rmtree(app.cfg.CONF.png_dir)
        except OSError as e:
            # Reraise unless ENOENT: No such file or directory
            # (ok if directory has already been deleted)
            if e.errno != errno.ENOENT:
                raise
            print e

    def test_empty_root(self):
        rv = self.app.get("/")
        self.assertIn('href="/energy/last/minute/"', rv.data)
        self.assertIn("302", rv.status)

    def test_empty_root_main(self):
        rv = self.app.get("/energy/last/minute/")
        self.assertIn("200", rv.status)
        self.assertIn(self.site, rv.data)
        rv = self.app.get("/network/last/minute/")
        self.assertIn("200", rv.status)
        self.assertIn("network", rv.data)
        rv = self.app.get("/foo/last/minute/")
        self.assertIn("404", rv.status)

if __name__ == '__main__':
    unittest.main()
