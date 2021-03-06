# -*- coding: utf-8 -*-
#
# Author: François Rossigneux <francois.rossigneux@inria.fr>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Set up the HDF5 server application instance."""

import sys
import signal
import thread
from threading import Thread
import ast
import flask
from kwapi.plugins import listen
from kwapi.utils import cfg, log
import v1
from hdf5_collector import HDF5_Collector
import hdf5_collector

LOG = log.getLogger(__name__)

app_opts = [
    cfg.MultiStrOpt('probes_endpoint',
                    required=True,
                    ),
    cfg.IntOpt('hdf5_port',
               required=True,
               ),
    cfg.StrOpt('driver_conf',
               required=True,
               ),
    cfg.StrOpt('log_file',
               required=True,
               ),
]

cfg.CONF.register_opts(app_opts)

writters = []

storePower = None
storeNetworkIn = None
storeNetworkOut = None


def make_app():
    """Instantiates Flask app, attaches collector database. """
    LOG.info('Starting HDF5')
    app = flask.Flask(__name__)
    app.register_blueprint(v1.blueprint, url_prefix='')

    # Parse the driver configuration
    per_outlet_nodes = {}
    parser = cfg.ConfigParser(cfg.CONF.driver_conf, {})
    parser.parse()
    for section, entries in parser.sections.iteritems():
        if section != 'DEFAULT' and 'pdu' in section:
            # Detect nodes with per_outlet monitoring
            probe_names = ast.literal_eval(entries['probes_names'][0])
            probes = ast.literal_eval(entries['probes'][0])
            notNoneProbe = None
            for p in probe_names:
                if p is not None:
                    notNoneProbe = p
            if notNoneProbe is not None and len(notNoneProbe) == 1:
                for i in range(0, len(probe_names)):
                    if probe_names[i] is not None:
                        name = probe_names[i][0].split('.')[-1].replace('-', '_')
                        probe = probes[i]
                        if name not in per_outlet_nodes:
                            per_outlet_nodes[name] = {'pdus': [], 'cons': {}}
                        per_outlet_nodes[name]['pdus'].append(probe)
    LOG.info('per outlet nodes: %s' % per_outlet_nodes.keys())
    # HDF5 Collectors
    app.storePower = HDF5_Collector('power', per_outlet_nodes)
    app.storeNetworkIn = HDF5_Collector('network_in', {})
    app.storeNetworkOut = HDF5_Collector('network_out', {})

    thread.start_new_thread(listen, (hdf5_collector.update_hdf5,))
    writters.append(Thread(target=app.storePower.write_datas,
                           name="PowerWritter"))
    writters.append(Thread(target=app.storeNetworkIn.write_datas,
                           name="NetworkInWritter"))
    writters.append(Thread(target=app.storeNetworkOut.write_datas,
                           name="NetworkOutWritter"))
    for writter in writters:
        writter.daemon = True
        writter.start()

    @app.before_request
    def attach_config():
        flask.request.storePower = app.storePower
        flask.request.storeNetworkIn = app.storeNetworkIn
        flask.request.storeNetworkOut = app.storeNetworkOut
    return app

def signal_handler(signal, frame):
    LOG.info("FLUSH DATAS")
    for data_type in hdf5_collector.buffered_values:
        hdf5_collector.buffered_values[data_type].put('STOP')
    for i in range(len(writters)):
        writters[0].join()
        LOG.info("DATA from %s FLUSHED" % writters[0].name)
        del writters[0]
    sys.exit(0)

def start():
    """Starts Kwapi HDF5."""
    cfg.CONF(sys.argv[1:],
             project='kwapi',
             default_config_files=['/etc/kwapi/hdf5.conf'])
    log.setup(cfg.CONF.log_file)
    signal.signal(signal.SIGINT, signal_handler)
    root = make_app()
    root.run(host='0.0.0.0', port=cfg.CONF.hdf5_port)
    signal.pause()
