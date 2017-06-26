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

import json
import urllib2
import time

from kwapi.utils import log
from driver import Driver

LOG = log.getLogger(__name__)


class Json_url(Driver):
    """Driver for Json URL interface."""

    def __init__(self, probe_ids, probe_names, probe_data_type, **kwargs):
        """Initializes the Json URL driver.
        Keyword arguments:
        probe_ids -- list containing the probes IDs
                     (a wattmeter monitor sometimes several probes)
        kwargs -- keyword (url) defining the Json URL driver parameters

        """
        Driver.__init__(self, probe_ids, probe_names, probe_data_type, kwargs)

    def run(self):
        """Starts the driver thread."""
        last_timestamps = {}
        while not self.stop_request_pending():
            req_time = time.time()
            LOG.debug('Requesting at %s' % str(req_time))
            try:
                hret = None
                json_str = None
                json_content = None
                hret = urllib2.urlopen(self.kwargs.get('url'))
                json_str = hret.read()
                json_content = json.loads(json_str)
            except Exception as e:
                LOG.error('Error while fetching json')
                LOG.error('http_url: %s' % self.kwargs.get('url'))
                LOG.error('http_info: %s' % str(hret.info()))
                LOG.error('http_code: %s' % str(hret.getcode()))
                LOG.error('http_result: %s' % str(hret))
                LOG.error('http_data: %s' % str(json_str))
                LOG.error(str(e))
            else:
                for i in range(len(self.probes_names)):
                    probe = json_content.get(self.probes_names[i][0].split('.')[1])
                    # Grid5000 specific as we declare probes as site.cluster-#
                    if probe:
                        if probe['timestamp'] != last_timestamps.get(i, -1):
                            measurements = self.create_measurements(self.probe_ids[i],
                                                                probe['timestamp'],
                                                                probe['watt'])
                            self.send_measurements(self.probe_ids[i], measurements)
                            last_timestamps[i] = probe['timestamp']

            duration = max(0, 0.7-(time.time()-req_time))
            LOG.debug('Sleeping for %s' % str(duration))
            time.sleep(duration)
