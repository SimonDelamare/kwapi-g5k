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

"""Defines functions to build and update rrd database and graph."""

import collections
import colorsys
import errno
import os
from threading import Lock
import struct
import time
import uuid

import rrdtool

from kwapi.utils import cfg, log

LOG = log.getLogger(__name__)

rrd_opts = [
    cfg.BoolOpt('signature_checking',
                required=True,
                ),
    cfg.FloatOpt('kwh_price',
                 required=True,
                 ),
    cfg.IntOpt('hue',
               required=True,
               ),
    cfg.IntOpt('max_watts',
               required=True,
               ),
    cfg.MultiStrOpt('probes_endpoint',
                    required=True,
                    ),
    cfg.MultiStrOpt('watch_probe',
                    required=False,
                    ),
    cfg.StrOpt('currency',
               required=True,
               ),
    cfg.StrOpt('driver_metering_secret',
               required=True,
               ),
    cfg.StrOpt('png_dir',
               required=True,
               ),
    cfg.StrOpt('rrd_dir',
               required=True,
               ),
]

cfg.CONF.register_opts(rrd_opts)

scales = collections.OrderedDict()
# Resolution = 1 second
scales['minute'] = {'interval': 300, 'resolution': 1, 'label': '5 minutes'},
# Resolution = 10 seconds
scales['hour'] = {'interval': 3600, 'resolution': 10, 'label': 'hour'},
# Resolution = 15 minutes
scales['day'] = {'interval': 86400, 'resolution': 900, 'label': 'day'},
# Resolution = 2 hours
scales['week'] = {'interval': 604800, 'resolution': 7200, 'label': 'week'},
# Resolution = 6 hours
scales['month'] = {'interval': 2678400, 'resolution': 21600, 'label': 'month'},
# Resolution = 1 week
scales['year'] = {'interval': 31622400, 'resolution': 604800, 'label': 'year'},

probes_set = set()
probe_colors = {}
lock = Lock()


def color_generator(nb_colors):
    """Generates colors."""
    min_brightness = 50-nb_colors*15/2.0
    if min_brightness < 5:
        min_brightness = 5
    max_brightness = 50+nb_colors*15/2.0
    if max_brightness > 95:
        max_brightness = 95
    if nb_colors <= 1:
        min_brightness = 50
        step = 0
    else:
        step = (max_brightness-min_brightness) / (nb_colors-1.0)
    i = min_brightness
    while int(i) <= max_brightness:
        rgb = colorsys.hsv_to_rgb(cfg.CONF.hue/360.0,
                                  1,
                                  i/100.0)
        rgb = tuple([int(x*255) for x in rgb])
        yield '#' + struct.pack('BBB', *rgb).encode('hex')
        i += step
        if step == 0:
            break


def create_dirs():
    """Creates all required directories."""
    directories = []
    directories.append(cfg.CONF.png_dir)
    directories.append(cfg.CONF.rrd_dir)
    # Build a list of directory names
    # Avoid loop in try block (problem if exception occurs), and avoid multiple
    # try blocks (too long)
    for scale in scales.keys():
        directories.append(cfg.CONF.png_dir + '/' + scale)
    # Create each directory in a try block, and continue if directory already
    # exist
    for directory in directories:
        try:
            os.makedirs(directory)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise


def get_png_filename(scale, probe):
    """Returns the png filename."""
    return cfg.CONF.png_dir + '/' + scale + '/' + \
        str(uuid.uuid5(uuid.NAMESPACE_DNS, str(probe))) + '.png'


def get_rrd_filename(probe):
    """Returns the rrd filename."""
    return cfg.CONF.rrd_dir + '/' + str(uuid.uuid5(uuid.NAMESPACE_DNS,
                                        str(probe))) + '.rrd'


def create_rrd_file(filename):
    """Creates a RRD file."""
    if not os.path.exists(filename):
        args = [filename,
                '--start', '0',
                '--step', '1',
                # Heartbeat = 600 seconds, Min = 0, Max = Unlimited
                'DS:w:GAUGE:600:0:U',
                ]
        for scale in scales.keys():
            args.append('RRA:AVERAGE:0.5:%s:%s'
                        % (scales[scale][0]['resolution'],
                           scales[scale][0]['interval'] /
                           scales[scale][0]['resolution']))
        rrdtool.create(args)


def update_rrd(probe, watts):
    """Updates RRD file associated with this probe."""
    if not probe in probes_set:
        color_seq = color_generator(len(probes_set)+1)
        lock.acquire()
        probes_set.add(probe)
        for probe in sorted(probes_set, reverse=True):
            probe_colors[probe] = color_seq.next()
        lock.release()
    filename = cfg.CONF.rrd_dir + '/' + \
        str(uuid.uuid5(uuid.NAMESPACE_DNS, str(probe))) + '.rrd'
    if not os.path.isfile(filename):
        create_rrd_file(filename)
    try:
        rrdtool.update(filename, 'N:%s' % watts)
    except rrdtool.error as e:
        LOG.error('Error updating RRD: %s' % e)


def build_graph(scale, probes, summary=True):
    """Builds the graph for the probes, or a summary graph."""
    if not isinstance(probes, list):
        probes = [probes]
    probes = [probe for probe in probes if probe in probes_set]
    if scale not in scales.keys() or len(probes_set) == 0:
        return
    # Only one probe
    if len(probes) == 1 and not summary:
        png_file = get_png_filename(scale, probes[0])
    # All probes
    elif not probes or set(probes) == probes_set:
        png_file = cfg.CONF.png_dir + '/' + scale + '/summary.png'
        probes = list(probes_set)
    # Specific combinaison of probes, so store the file in tmp directory
    else:
        png_file = '/tmp/' + str(uuid.uuid4()) + '.png'
    # Get the file from cache
    if os.path.exists(png_file) and os.path.getmtime(png_file) > \
            time.time() - scales[scale][0]['resolution']:
        LOG.info('Retrieve PNG graph from cache')
        return png_file
    # Build required (PNG file not found or outdated)
    scale_label = ' (' + scales[scale][0]['label'] + ')'
    if summary:
        # Specific arguments for summary graph
        args = [png_file,
                '--title', 'Summary' + scale_label,
                '--width', '694',
                '--height', '261',
                ]
    else:
        # Specific arguments for probe graph
        args = [png_file,
                '--title', probes[0] + scale_label,
                '--width', '497',
                '--height', '187',
                '--upper-limit', str(cfg.CONF.max_watts),
                ]
    # Common arguments
    args += ['--start', '-' + str(scales[scale][0]['interval']),
             '--end', 'now',
             '--full-size-mode',
             '--imgformat', 'PNG',
             '--alt-y-grid',
             '--vertical-label', 'Watts',
             '--lower-limit', '0',
             '--rigid',
             ]
    if scale == 'minute':
        args += ['--x-grid', 'SECOND:30:MINUTE:1:MINUTE:1:0:%H:%M']
    cdef_watt = 'CDEF:watt='
    cdef_watt_with_unknown = 'CDEF:watt_with_unknown='
    graph_lines = []
    stack = False
    probe_list = sorted(probes, reverse=True)
    for probe in probe_list:
        probe_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, probe)
        rrd_file = get_rrd_filename(probe)
        # Data source
        args.append('DEF:watt_with_unknown_%s=%s:w:AVERAGE'
                    % (probe_uuid, rrd_file))
        # Data source without unknown values
        args.append('CDEF:watt_%s=watt_with_unknown_%s,UN,0,watt_with_'
                    'unknown_%s,IF'
                    % (probe_uuid, probe_uuid, probe_uuid))
        # Prepare CDEF expression of total watt consumption
        cdef_watt += 'watt_%s,' % probe_uuid
        cdef_watt_with_unknown += 'watt_with_unknown_%s,' % probe_uuid
        # Draw the area for the probe
        color = probe_colors[probe]
        args.append('AREA:watt_with_unknown_%s%s::STACK'
                    % (probe_uuid, color + 'AA'))
        if not stack:
            graph_lines.append('LINE:watt_with_unknown_%s%s::'
                               % (probe_uuid, color))
            stack = True
        else:
            graph_lines.append('LINE:watt_with_unknown_%s%s::STACK'
                               % (probe_uuid, color))
    if len(probe_list) >= 2:
        # Prepare CDEF expression by adding the required number of '+'
        cdef_watt += '+,' * int(len(probe_list)-2) + '+'
        cdef_watt_with_unknown += '+,' * int(len(probe_list)-2) + '+'
    args += graph_lines
    args.append(cdef_watt)
    args.append(cdef_watt_with_unknown)
    # Min watt
    args.append('VDEF:wattmin=watt_with_unknown,MINIMUM')
    # Max watt
    args.append('VDEF:wattmax=watt_with_unknown,MAXIMUM')
    # Partial average that will be displayed (ignoring unknown values)
    args.append('VDEF:wattavg_with_unknown=watt_with_unknown,AVERAGE')
    # Real average (to compute kWh)
    args.append('VDEF:wattavg=watt,AVERAGE')
    # Compute kWh for the probe
    # RPN expressions must contain DEF or CDEF variables, so we pop a
    # CDEF value
    args.append('CDEF:kwh=watt,POP,wattavg,1000.0,/,%s,3600.0,/,*'
                % str(scales[scale][0]['interval']))
    # Compute cost
    args.append('CDEF:cost=watt,POP,kwh,%f,*' % cfg.CONF.kwh_price)
    # Legend
    args.append('GPRINT:wattavg_with_unknown:Avg\: %3.1lf W')
    args.append('GPRINT:wattmin:Min\: %3.1lf W')
    args.append('GPRINT:wattmax:Max\: %3.1lf W')
    args.append('GPRINT:watt_with_unknown:LAST:Last\: %3.1lf W\j')
    args.append('TEXTALIGN:center')
    args.append('GPRINT:kwh:LAST:Total\: %lf kWh')
    args.append('GPRINT:cost:LAST:Cost\: %lf ' + cfg.CONF.currency)
    LOG.info('Build PNG graph')
    rrdtool.graph(args)
    return png_file
