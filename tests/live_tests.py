# coding=utf-8
import os
import kwapi.plugins.live.app as app
import unittest
import tempfile
import time
import socket
import shutil
import errno
from mock import patch, call
import json


class LiveTestCase(unittest.TestCase):
    job_api_json = """{{
      "uid": {job_id},
      "user_uid": "{user}",
      "user": "{user}",
      "walltime": 3600,
      "queue": "default",
      "state": "terminated",
      "project": "default",
      "types": [
        "deploy"
      ],
      "mode": "INTERACTIVE",
      "command": "",
      "submitted_at": {start},
      "started_at": {start},
      "stopped_at": {stop},
      "message": "FIFO scheduling OK",
      "properties": "((deploy = 'YES') AND maintenance = 'NO') AND production = 'NO'",
      "directory": "/home/{user}",
      "events": [
      ],
      "links": [
        {{
          "rel": "self",
          "href": "/sid/sites/{site}/jobs/{job_id}",
          "type": "application/vnd.grid5000.item+json"
        }},
        {{
          "rel": "parent",
          "href": "/sid/sites/{site}",
          "type": "application/vnd.grid5000.item+json"
        }}
      ],
      "resources_by_type": {{
        "cores": [
          "{node}.{site}.grid5000.fr",
          "{node}.{site}.grid5000.fr",
          "{node}.{site}.grid5000.fr",
          "{node}.{site}.grid5000.fr"
        ]
      }},
      "assigned_nodes": [
        "{node}.{site}.grid5000.fr"
      ]
    }}"""

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
        job_json = self.job_api_json.format(node="bar-1", site=self.site,
                                            job_id=1, user="foo",
                                            start=int(time.time() - 3600),
                                            stop=int(time.time()))

        patch("kwapi.plugins.live.v1.get_resource_attributes",
              return_value=json.loads(job_json)).start()
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
        self.appp = app
        self.live = app.live
        my_app = app.make_app()
        self.app = my_app.test_client()

    def add_data(self, t=int(time.time())):
        probe = "%s.%s" % (self.site, "bar-1")
        pdu = "%s.%s.%d" % (self.site, "pdu", 1)
        switch = "%s.%s.%d-%d" % (self.site, "switch", 1, 1)
        self.add_value(pdu, [probe], 'power', t, 1,
                       {'type': "power", 'unit': "KW"})
        self.add_value(switch, [probe], 'network_in', t, 1,
                       {'type': "network_in", 'unit': "B"})
        self.add_value(switch, [probe], 'network_out', t, 1,
                       {'type': "network_out", 'unit': "B"})

    def tearDown(self):
        patch.stopall()
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

    def test_empty_probe(self):
        rv = self.app.get("/energy/probe/bar-1/")
        self.assertIn("404", rv.status)
        rv = self.app.get("/network/probe/bar-1/")
        self.assertIn("404", rv.status)
        rv = self.app.get("/foo/probe/bar-1/")
        self.assertIn("404", rv.status)

    def test_empty_zip(self):
        # Return an empty zip file
        rv = self.app.get("/zip/")
        self.assertIn("200", rv.status)
        rv = self.app.get("/zip/?probes=bar-1")
        self.assertIn("200", rv.status)
        self.add_data()
        rv = self.app.get("/zip/")
        self.assertIn("200", rv.status)

    def test_empty_metric_sum_graph(self):
        t = time.time()
        rv = self.app.get("/foo/summary-graph/%d/%d/" % (t - 300, t))
        self.assertIn("404", rv.status)
        rv = self.app.get("/energy/summary-graph/%d/%d/" % (t - 300, t))
        self.assertIn("404", rv.status)
        rv = self.app.get("/network/summary-graph/%d/%d/" % (t - 300, t))
        self.assertIn("404", rv.status)
        rv = self.app.get(
            "/energy/summary-graph/%d/%d/?probes=bar-1" % (t - 300, t))
        self.assertIn("404", rv.status)

    def test_metric_sum_graph(self):
        self.add_data()
        t = time.time()
        with tempfile.NamedTemporaryFile(suffix='.rrd') as probe_rrd:
            shutil.copy2("tests/rrds/bar-1.rrd", probe_rrd.name)
            with patch("kwapi.plugins.live.live.get_rrd_filename",
                       return_value=probe_rrd.name) as m:
                # Fail with 404 if unknown metric
                rv = self.app.get("/foo/summary-graph/%d/%d/" % (t - 300, t))
                self.assertIn("404", rv.status)
                m.reset_mock()
                # Return power 5m summary graph
                rv = self.app.get(
                    "/energy/summary-graph/%d/%d/" % (t - 300, t))
                self.assertIn("200", rv.status)
                m.assert_called_once_with("%s.pdu.1" % self.site, "power")
                m.reset_mock()
                rv = self.app.get(
                    "/network/summary-graph/%d/%d/" % (t - 300, t))
                self.assertIn("200", rv.status)
                calls = [call("%s.switch.1-1" % self.site, "network_out"),
                         call("%s.switch.1-1" % self.site, "network_in")]
                m.assert_has_calls(calls)
                m.reset_mock()
                rv = self.app.get(
                    "/energy/summary-graph/%d/%d/?probes=cacahuete.bar-1" % (
                    t - 300, t))
                self.assertIn("200", rv.status)
                m.assert_called_once_with("%s.pdu.1" % self.site, "power")
                m.reset_mock()
                rv = self.app.get(
                    "/network/summary-graph/%d/%d/?probes=cacahuete.bar-1" % (
                    t - 300, t))
                self.assertIn("200", rv.status)
                m.assert_has_calls(calls)
                m.reset_mock()


if __name__ == '__main__':
    unittest.main()
