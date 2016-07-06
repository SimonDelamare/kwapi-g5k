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
    def add_value(self, probe, probes_names, data_type, timestamp, metrics,
                  params):
        return self.h5c.update_hdf5(probe, probes_names, data_type,
                               timestamp, metrics, params)

    def setUp(self):
        self.log_file_fd, app.cfg.CONF.log_file = tempfile.mkstemp()
        app.cfg.CONF.hdf5_dir = tempfile.mkdtemp()
        self.endpoint_fd, probes_endpoint = tempfile.mkstemp()
        app.cfg.CONF.probes_endpoint = ["ipc://" + probes_endpoint]
        app.cfg.CONF.chunk_size = 1
        # HDF5 dates
        app.cfg.CONF.start_date = "2014/11/01"
        app.cfg.CONF.split_days = 0
        app.cfg.CONF.split_weeks = 0
        app.cfg.CONF.split_months = 1
        my_app = app.make_app()
        self.app = my_app.test_client()
        self.site = socket.getfqdn().split('.')
        self.site = self.site[1] if len(self.site) >= 2 else self.site[0]
        self.h5c = app.hdf5_collector

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
        except OSError as e:
            # Reraise unless ENOENT: No such file or directory
            # (ok if directory has already been deleted)
            if e.errno != errno.ENOENT:
                raise
            print e

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
        self.add_data(t)
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
                     u'available_on': [u'1-1.switch.%s.grid5000.fr' % self.site],
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
                     u'available_on': [u'1-1.switch.%s.grid5000.fr' % self.site],
                     u'step': 1,
                     u'timeseries': [
                         {u'pdp_per_row': 1,
                          u'cf': u'LAST',
                          u'xff': 0}],
                     u'type': u'metric'}]}
        self.assertDictEqual(a, stringtojson(rv))

    def test_metric(self):
        self.add_data()
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
        rv = self.app.get('/network_in/', headers={"Accept": "grid5000"})
        a = {u'uid': u'network_in',
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
             u'available_on': [u'1-1.switch.%s.grid5000.fr' % self.site],
             u'step': 1,
             u'timeseries': [
                 {u'pdp_per_row': 1,
                  u'cf': u'LAST',
                  u'xff': 0}],
             u'type': u'metric'}
        self.assertDictEqual(a, stringtojson(rv))
        rv = self.app.get('/network_out/', headers={"Accept": "grid5000"})
        a = {u'uid': u'network_out',
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
             u'available_on': [u'1-1.switch.%s.grid5000.fr' % self.site],
             u'step': 1,
             u'timeseries': [
                 {u'pdp_per_row': 1,
                  u'cf': u'LAST',
                  u'xff': 0}],
             u'type': u'metric'}
        self.assertDictEqual(a, stringtojson(rv))

    def test_unknown_metric(self):
        rv = self.app.get('/foo/')
        assert "404" in rv.status

    def test_metric_timeseries(self):
        t = int(time.time())
        self.add_data(t)
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

    def test_metric_timeseries_only(self):
        t = int(time.time())
        self.add_data(t)
        rv = self.app.get('/power/timeseries/?only=bar-1', headers={"Accept": "grid5000"})
        a = {u'items': [
            {u'from': t-24*3600,
             u'uid': u'bar-1',
             u'links': [
                 {
                     u'href': u'/sid/sites/%s/metrics/power/timeseries/bar-1' % self.site,
                     u'type': u'application/vnd.fr.grid5000.api.Timeseries+json;level=1',
                     u'rel': u'self'},
                 {u'href': u'/sid/sites/%s/metrics/power' % self.site,
                  u'type': u'application/vnd.fr.grid5000.api.Metric+json;level=1',
                  u'rel': u'parent'}],
             u'type': u'timeseries',
             u'to': t,
             u'values': [1],
             u'timestamps': [t],
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
        # Round timestamp to 0.1
        b['items'][0]['timestamps'][0] = int(b['items'][0]['timestamps'][0]*10/10)
        self.assertDictEqual(a, b)
        # With wrong time
        t = int(time.time())
        rv = self.app.get('/power/timeseries/?only=bar-1&from=foo&to=fooo',
                          headers={"Accept": "grid5000"})
        a['items'][0]['from'] = t-24*3600
        a['items'][0]['to'] = t
        b = stringtojson(rv)
        # Round of time value for easy testing...
        b['items'][0]['from'] = int(b['items'][0]['from'])
        b['items'][0]['to'] = int(b['items'][0]['to'])
        # Round timestamp to 0.1
        b['items'][0]['timestamps'][0] = int(b['items'][0]['timestamps'][0]*10/10)
        self.assertDictEqual(a, b)

    def test_content_type(self):
        rv = self.app.get("/", headers={"Accept": "grid5000"})
        self.assertEqual(rv.headers['Content-Type'],
                         'application/vnd.fr.grid5000.api.Collection+json;level=1')
        rv = self.app.get("/", headers={"Accept": "json"})
        self.assertEqual(rv.headers['Content-Type'],
                         'application/json')
        t = int(time.time())
        self.add_data(t)
        rv = self.app.get('/power/', headers={"Accept": "grid5000"})
        self.assertEqual(rv.headers['Content-Type'],
                         'application/vnd.fr.grid5000.api.Metric+json;level=1')
        rv = self.app.get("/power/", headers={"Accept": "json"})
        self.assertEqual(rv.headers['Content-Type'],
                         'application/json')
        rv = self.app.get('/power/timeseries', headers={"Accept": "grid5000"})
        self.assertEqual(rv.headers['Content-Type'],
                         'application/vnd.fr.grid5000.api.Collection+json;level=1')
        rv = self.app.get("/power/timeseries", headers={"Accept": "json"})
        self.assertEqual(rv.headers['Content-Type'],
                         'application/json')
        rv = self.app.get('/power/timeseries/?only=bar-1', headers={"Accept": "grid5000"})
        self.assertEqual(rv.headers['Content-Type'],
                         'application/vnd.fr.grid5000.api.Collection+json;level=1')
        rv = self.app.get("/power/timeseries/?only=bar-1", headers={"Accept": "json"})
        self.assertEqual(rv.headers['Content-Type'],
                         'application/json')

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
        rv = self.app.get("/network_in", headers={"Accept": "grid5000"})
        res = stringtojson(rv)
        probes = [u'1-1.gw.%s.grid5000.fr' % self.site]
        self.assertListEqual(probes, res["available_on"])
        rv = self.app.get("/network_in/timeseries/?only=gw-switch",
                          headers={"Accept": "grid5000"})
        res = stringtojson(rv)
        self.assertEqual(res["items"][0]["values"][0], 1)
        rv = self.app.get("/network_out/timeseries/?only=gw-switch",
                          headers={"Accept": "grid5000"})
        res = stringtojson(rv)
        self.assertEqual(res["items"][0]["values"][0], 2)

if __name__ == '__main__':
    unittest.main()
