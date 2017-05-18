import os
import kwapi.plugins.api.app as app
import unittest
import tempfile
import time
import json
import socket


class APITestCase(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.log_file_fd, app.cfg.CONF.log_file = tempfile.mkstemp()
        self.endpoint_fd, probes_endpoint = tempfile.mkstemp()
        app.cfg.CONF.probes_endpoint = ["ipc://" + probes_endpoint]
        my_app = app.make_app()
        self.col = app.collector
        self.app = my_app.test_client()
        self.site = socket.getfqdn().split('.')
        self.site = self.site[1] if len(self.site) >= 2 else self.site[0]

    def tearDown(self):
        self.col.database = {}
        os.close(self.log_file_fd)
        os.unlink(app.cfg.CONF.log_file)
        os.close(self.endpoint_fd)
        os.unlink(app.cfg.CONF.probes_endpoint[0][6:])

    def test_empty_root(self):
        rv = self.app.get('/')
        self.assertEqual("Welcome to Kwapi!", rv.data)

    def test_empty_probes_ids(self):
        rv = self.app.get('/probe-ids/')
        a = {u'probe_ids': []}
        self.assertEqual(a, json.loads(rv.data))

    def test_empty_probes(self):
        rv = self.app.get('/probes/')
        a = {u'probes': {}}
        self.assertEqual(a, json.loads(rv.data))

    def test_empty_probes_unknown(self):
        rv = self.app.get('/probes/foo/')
        a = {}
        self.assertEqual(a, json.loads(rv.data))    

    def test_empty_probes_metric_unknown(self):
        rv = self.app.get('/probes/foo/bar/')
        assert "404" in rv.status

    def add_value(self, probe, probes_names, data_type, timestamp, measure, params):
        return self.col.add(probe, probes_names, data_type, timestamp, measure, params)

    def test_probes(self):
        t = int(time.time())
        probe = u"%s.%s" % (self.site, "bar-1")
        self.add_value([probe], [probe], 'power', t, 1, {'type': "power", 'unit': "KW"})
        rv = self.app.get('/probes/')
        a = {u'probes': {
            u'power': {
                probe: dict(timestamp=t, type=u'power', unit=u'KW', value=1)
            }
        }
        }
        b = json.loads(rv.data)
        self.assertEqual(a, b)

    def test_probes_ids(self):
        t = int(time.time())
        probe = u"%s.%s" % (self.site, "bar-1")
        self.add_value([probe], [probe], 'power', t, 1, {'type': "power", 'unit': "KW"})
        rv = self.app.get('/probe-ids/')
        a = {u'probe_ids': [probe]}
        self.assertEqual(a, json.loads(rv.data))

    def test_probes_name(self):
        t = int(time.time())
        probe = u"%s.%s" % (self.site, "bar-1")
        self.add_value([probe], [probe], 'power', t, 1, {'type': "power", 'unit': "KW"})
        rv = self.app.get('/probes/%s.bar-1/' % self.site)
        a = {u'power': {
                probe: dict(timestamp=t, type=u'power', unit=u'KW', value=1)
            }
        }
        b = json.loads(rv.data)
        self.assertEqual(a, b)

    def test_probes_name_metric(self):
        t = int(time.time())
        probe = u"%s.%s" % (self.site, "bar-1")
        self.add_value([probe], [probe], 'power', t, 1, {'type': "power", 'unit': "KW"})
        self.add_value([probe], [probe], 'network_in', t, 1, {'type': "network_in", 'unit': "B"})
        self.add_value([probe], [probe], 'network_out', t, 1, {'type': "network_out", 'unit': "B"})
        rv = self.app.get('/probes/%s.bar-1/power/' % self.site)
        a = {u'power': {
                probe: dict(timestamp=t, type=u'power', unit=u'KW', value=1)
            }
        }
        b = json.loads(rv.data)
        self.assertEqual(a, b)

    def test_inter_switch(self):
        """Test inter-switch links on the following topology
        gw.site [1/1] <=> [1/2] switch.site
        Traffic:
        * from switch to gw: 1B
        * from gw to switch: 2B
        """
        t = int(time.time())
        probe = "%s.%s" % (self.site, "gw-switch")
        switch = "%s.%s.%d-%d" % (self.site, "gw", 1, 1)
        self.add_value(switch, [probe], 'network_in', t, 1,
                       {'type': "network_in", 'unit': "B"})
        self.add_value(switch, [probe], 'network_out', t, 2,
                       {'type': "network_out", 'unit': "B"})
        rv = self.app.get('/probes/%s.gw-switch/network_in/' % self.site)
        a = {u'network_in': {
            u'%s.gw-switch' % self.site: {
                u'timestamp': t,
                u'type': u'network_in',
                u'value': 1,
                u'unit': u'B'}}}
        b = json.loads(rv.data)
        self.assertDictEqual(a, b)
        rv = self.app.get('/probes/%s.gw-switch/network_out/' % self.site)
        a = {u'network_out': {
            u'%s.gw-switch' % self.site: {
                u'timestamp': t,
                u'type': u'network_out',
                u'value': 2,
                u'unit': u'B'}}}
        b = json.loads(rv.data)
        self.assertDictEqual(a, b)

if __name__ == '__main__':
    unittest.main()
