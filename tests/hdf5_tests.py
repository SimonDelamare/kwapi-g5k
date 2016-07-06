import os
import kwapi.plugins.hdf5.app as app
import kwapi.plugins.hdf5.hdf5_collector as h5c
import unittest
import tempfile
import time
import json
import socket
import shutil
import errno
import collections


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
        self.storePower = my_app.storePower
        self.storeNetworkIn = my_app.storeNetworkIn
        self.storeNetworkOut = my_app.storeNetworkOut
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
        h5c.clear_probes()

    def add_value(self, probe, probes_names, data_type, timestamp, metrics,
                  params):
        return h5c.update_hdf5(probe, probes_names, data_type,
                                           timestamp, metrics, params)

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
             u'total': 0
             }
        self.assertDictEqual(a, stringtojson(rv))

    def test_root(self):
        t = int(time.time())
        probe = "%s.%s" % (self.site, "bar-1")
        pdu = "%s.%s.%d" % (self.site, "pdu", 1)
        switch = "%s.%s.%d" % (self.site, "switch", 1)
        self.add_value(pdu, [probe], 'power', t, 1, {'type': "power", 'unit': "KW"})
        self.add_value(switch, [probe], 'network_in', t, 1,
                       {'type': "network_in", 'unit': "B"})
        self.add_value(switch, [probe], 'network_out', t, 1,
                       {'type': "network_in", 'unit': "B"})
        rv = self.app.get("/", headers={"Accept": "grid5000"})
        a = {
            u'items':
                [
                    {u'uid': u'power',
                     u'links': [
                         {u'href': u'/sid/sites/%s/metrics/power' % self.site,
                          u'type': u'application/vnd.fr.grid5000.api.Metric+json;level=1',
                          u'rel': u'self'},
                         {u'href': u'/sid/sites/%s/metrics/power/timeseries' % self.site,
                          u'type': u'application/vnd.fr.grid5000.api.Collection+json;level=1',
                          u'rel': u'collection',
                          u'title': u'timeseries'},
                         {u'href': u'/sid/sites/%s' % self.site,
                          u'type': u'application/vnd.fr.grid5000.api.Site+json;level=1',
                          u'rel': u'parent'}],
                     u'available_on': [u'1.pdu.%s.grid5000.fr'% self.site],
                     u'step': 1,
                     u'timeseries': [
                         {u'pdp_per_row': 1,
                          u'cf': u'LAST',
                          u'xff': 0}],
                     u'type': u'metric'},
                    {u'uid': u'network_in',
                     u'links': [
                         {u'href': u'/sid/sites/%s/metrics/network_in' % self.site,
                          u'type': u'application/vnd.fr.grid5000.api.Metric+json;level=1',
                          u'rel': u'self'},
                         {u'href': u'/sid/sites/%s/metrics/network_in/timeseries' % self.site,
                          u'type': u'application/vnd.fr.grid5000.api.Collection+json;level=1',
                          u'rel': u'collection',
                          u'title': u'timeseries'},
                         {u'href': u'/sid/sites/%s' % self.site,
                          u'type': u'application/vnd.fr.grid5000.api.Site+json;level=1',
                          u'rel': u'parent'}],
                     u'available_on': [u'1.switch.%s.grid5000.fr' % self.site],
                     u'step': 1,
                     u'timeseries': [
                         {u'pdp_per_row': 1,
                          u'cf': u'LAST',
                          u'xff': 0}],
                     u'type': u'metric'},
                    {u'uid': u'network_out',
                     u'links': [
                         {u'href': u'/sid/sites/%s/metrics/network_out' % self.site,
                          u'type': u'application/vnd.fr.grid5000.api.Metric+json;level=1',
                          u'rel': u'self'},
                         {u'href': u'/sid/sites/%s/metrics/network_out/timeseries' % self.site,
                          u'type': u'application/vnd.fr.grid5000.api.Collection+json;level=1',
                          u'rel': u'collection',
                          u'title': u'timeseries'},
                         {u'href': u'/sid/sites/%s' % self.site,
                          u'type': u'application/vnd.fr.grid5000.api.Site+json;level=1',
                          u'rel': u'parent'}],
                     u'available_on': [u'1.switch.%s.grid5000.fr' % self.site],
                     u'step': 1,
                     u'timeseries': [
                         {u'pdp_per_row': 1,
                          u'cf': u'LAST',
                          u'xff': 0}],
                     u'type': u'metric'}]}
        self.assertDictEqual(a, stringtojson(rv))

    def test_metric(self):
        t = int(time.time())
        probe = "%s.%s" % (self.site, "bar-1")
        pdu = "%s.%s.%d" % (self.site, "pdu", 1)
        switch = "%s.%s.%d" % (self.site, "switch", 1)
        self.add_value(pdu, [probe], 'power', t, 1, {'type': "power", 'unit': "KW"})
        self.add_value(switch, [probe], 'network_in', t, 1,
                       {'type': "network_in", 'unit': "B"})
        self.add_value(switch, [probe], 'network_out', t, 1,
                       {'type': "network_in", 'unit': "B"})
        rv = self.app.get('/power/', headers={"Accept": "grid5000"})
        a = {u'uid': u'power',
             u'links': [
                 {u'href': u'/sid/sites/%s/metrics/power' % self.site,
                  u'type': u'application/vnd.fr.grid5000.api.Metric+json;level=1',
                  u'rel': u'self'},
                 {u'href': u'/sid/sites/%s/metrics/power/timeseries' % self.site,
                  u'type': u'application/vnd.fr.grid5000.api.Collection+json;level=1',
                  u'rel': u'collection',
                  u'title': u'timeseries'},
                 {u'href': u'/sid/sites/%s' % self.site,
                  u'type': u'application/vnd.fr.grid5000.api.Site+json;level=1',
                  u'rel': u'parent'}],
             u'available_on': [u'1.pdu.%s.grid5000.fr' % self.site],
             u'step': 1,
             u'timeseries': [
                 {u'pdp_per_row': 1,
                  u'cf': u'LAST',
                  u'xff': 0}],
             u'type': u'metric'}
        self.assertDictEqual(a, stringtojson(rv))

    def test_metric_timeseries(self):
        t = int(time.time())
        self.maxDiff = None
        probe = "%s.%s" % (self.site, "bar-1")
        pdu = "%s.%s.%d" % (self.site, "pdu", 1)
        switch = "%s.%s.%d" % (self.site, "switch", 1)
        self.add_value(pdu, [probe], 'power', t, 1, {'type': "power", 'unit': "KW"})
        self.add_value(switch, [probe], 'network_in', t, 1,
                       {'type': "network_in", 'unit': "B"})
        self.add_value(switch, [probe], 'network_out', t, 1,
                       {'type': "network_in", 'unit': "B"})
        rv = self.app.get('/power/timeseries/', headers={"Accept": "grid5000"})
        a = {u'items': [
            {u'from': t,
             u'uid': u'bar-1',
             u'links': [
                 {u'href': u'/sid/sites/%s/metrics/power/timeseries/bar-1' % self.site,
                  u'type': u'application/vnd.fr.grid5000.api.Timeseries+json;level=1',
                  u'rel': u'self'},
                 {u'href': u'/sid/sites/%s/metrics/power' % self.site,
                  u'type': u'application/vnd.fr.grid5000.api.Metric+json;level=1',
                  u'rel': u'parent'}],
             u'type': u'timeseries',
             u'to': t,
             u'values': [],
             u'timestamps': [],
             u'resolution': 1}],
             u'total': 1,
             u'links': [
                 {u'href': u'/sid/%s' % self.site,
                  u'type': u'application/vnd.fr.grid5000.api.Collection+json;level=1',
                  u'rel': u'self'},
                 {u'href': u'/sid/sites/%s' % self.site,
                  u'type': u'application/vnd.fr.grid5000.api.Metric+json;level=1',
                  u'rel': u'parent'}],
             u'offset': 0}
        b = stringtojson(rv)
        # Round of time value for easy testing...
        b['items'][0]['from'] = int(b['items'][0]['from'])
        b['items'][0]['to'] = int(b['items'][0]['to'])
        self.assertDictEqual(a, b)

if __name__ == '__main__':
    unittest.main()
