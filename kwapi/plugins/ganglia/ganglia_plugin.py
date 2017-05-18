# -*- coding: utf-8 -*-
#
# Author: Clement Parisot <clement.parisot@inria.fr>
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

"""Export metrics to Ganglia server."""

import socket
from kwapi.utils import cfg, log
from ganglia import GMetric

LOG = log.getLogger(__name__)

ganglia_opts = [
    cfg.BoolOpt('signature_checking',
                required=True,
                ),
    cfg.StrOpt('ganglia_server',
               required=True,
               ),
    cfg.MultiStrOpt('watch_probe',
                    required=False,
                    ),
    cfg.StrOpt('driver_metering_secret',
               required=True,
               ),
    cfg.StrOpt('metric_name',
               required=True,
               ),
    cfg.StrOpt('metric_units',
               required=True,
               ),
    cfg.StrOpt('metric_type',
               required=True,
               ),
]
cfg.CONF.register_opts(ganglia_opts)
hostname = socket.getfqdn().split('.')
site = hostname[1] if len(hostname) >= 2 else hostname[0]

class GangliaPlugin:
    """Ganglia plugin push data from Kwapi to Ganglia server"""

    def __init__(self):
        """Initializes Ganglia server address."""
        LOG.info('Starting Ganglia Plugin')
        self.ganglia = GMetric(cfg.CONF.ganglia_server)
        self.metric_name = cfg.CONF.metric_name
        self.metric_units = cfg.CONF.metric_units
        if not cfg.CONF.metric_type in ['string', 'int8', 'uint8', 'int16', \
                                        'uint16', 'int32', 'uint32', 'float', \
                                        'double']:
            self.metric_type = 'uint16'
        else:
            self.metric_type = cfg.CONF.metric_type
        self.ip_probe = {}
        LOG.debug('Server:', self.ganglia,
                  'metric_name:', self.metric_name,
                  'metric_units', self.metric_units,
                  'metric_type', self.metric_type)

    def update_rrd(self, probe_uid, probes_names, data_type, timestamp,
                   metrics, params):
        """Retrieve hostname and address"""
        if not data_type == 'power':
            return
        if not type(probes_names) == list:
            probes_names = [probes_names]
        if len(probes_names) > 1:
            # Multiprobes are not exported
            return
        for probe in probes_names:
            probe_site = probe.split('.')[0]
            probe_id = str(".".join(probe.split('.')[1:]))
            if probe_id not in self.ip_probe:
                probe_hostname = "%s.%s.grid5000.fr" % (probe_id, probe_site)
                try:
                    ip = socket.gethostbyname(probe_hostname)
                    self.ip_probe[probe_id] = (ip, probe_hostname)
                except Exception as e:
                    LOG.error("Fail to retrieve %s ip: %s", probe_hostname, e)
                    self.ip_probe[probe_id] = None
                    continue
            if not self.ip_probe[probe_id]:
                continue
            # Convert metrics to integer, float or string
            if 'int' in self.metric_type:
                metrics = int(metrics)
            elif 'float' in self.metric_type:
                metrics = float(metrics)
            elif 'double' in self.metric_type:
                metrics = float(metrics)
            else:
                metrics = str(metrics)
            self.ganglia.send(
                name=self.metric_name,
                units=self.metric_units,
                type=self.metric_type,
                value=metrics,
                hostname='%s:%s' % (self.ip_probe[probe_id][0],
                                    self.ip_probe[probe_id][1]),
                spoof=True
            )
        return
