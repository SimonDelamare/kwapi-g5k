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

"""This blueprint defines all URLs and answers."""

import collections
import os
import shutil
import socket
import tempfile
import time
import zipfile

from execo_g5k.api_utils import get_resource_attributes
import flask
from flask import flash
from jinja2 import TemplateNotFound

from kwapi.utils import cfg, log
import live
sites = []

web_opts = [
    cfg.IntOpt('refresh_interval',
               required=True,
               ),
    cfg.StrOpt('png_dir',
               required=True,
               ),
    cfg.StrOpt('g5k_sites',
               required=True,
               ),
]

cfg.CONF.register_opts(web_opts)
LOG = log.getLogger(__name__)

blueprint = flask.Blueprint('v1', __name__, static_folder='static')

@blueprint.route('/')
def welcome():
    """Shows specified page."""
    return flask.redirect(flask.url_for('v1.welcome_scale',
                                        metric='energy',
                                        scale='minute'))


@blueprint.route('/<metric>/last/<scale>/')
def welcome_scale(metric, scale):
    """Shows a specific scale of a probe."""
    if metric == 'energy':
        probes = flask.request.probes_power
    elif metric == 'network':
        probes = flask.request.probes_network
    else:
        flask.abort(404)
    # if live.contains_multiprobes(probes) and metric == 'energy':
    #    flash('Multiprobes somewhere!') 
    try:
        return flask.render_template('index.html',
                                     hostname=flask.request.hostname,
                                     metric=metric,
                                     probes=sorted(probes),
                                     #  key=lambda x: (x.split('.')[1].split('-')[0],
                                     #  int(x.split('.')[1].split('-')[1]))),
                                     refresh=cfg.CONF.refresh_interval,
                                     scales=flask.request.scales,
                                     sites=sites,
                                     scale=scale,
                                     start=int(time.time()) - flask.request.scales[scale][0]['interval'],
                                     end=int(time.time()),
                                     view='scale')
    except TemplateNotFound:
        flask.abort(404)


@blueprint.route('/<metric>/probe/<probe>/')
def welcome_probe(metric, probe):
    """Shows all graphs of a probe."""                                              
    if metric == 'energy':                                                     
        probes = flask.request.probes_power                                    
    elif metric == 'network':                                                  
        probes = flask.request.probes_network                                  
    else:                                                                      
        flask.abort(404) 
    if live.contains_multiprobes([probe]) and metric == 'energy':
        flash("Multiprobes somewhere !")
    if probe not in probes:
        flask.abort(404)
    try:
        scales = collections.OrderedDict()
        for scale in flask.request.scales:
            scales[scale] = {
                'start': int(time.time()) - flask.request.scales[scale][0]['interval'],
                'end': int(time.time())
            }
        return flask.render_template('index.html',
                                     hostname=flask.request.hostname,
                                     metric=metric,
                                     probe=probe,
                                     refresh=cfg.CONF.refresh_interval,
                                     scales=scales,
                                     sites=sites,
                                     view='probe')
    except TemplateNotFound:
        flask.abort(404)

def filter_network_interface(probe):
    # Return hostname without the interface
    # IN: 'cacahuete.griffon-2-eth0'
    # OUT: 'nancy.griffon-2'
    return probe.split(".")[0] + "." + "-".join(probe.split(".")[1].split("-")[:2])


@blueprint.route('/nodes/<job>/<metric>/')
def get_nodes(job, metric):
    """Returns nodes assigned to a job."""
    site = socket.getfqdn().split('.')
    site = site[1] if len(site) >= 2 else site[0]
    path = '/sites/' + site + '/jobs/' + job
    job_properties = get_resource_attributes(path)
    nodes = job_properties['assigned_nodes']
    if "network" in metric:
        probes = []
        for node in nodes:
            selectedProbe = site + '.' + node.split('.')[0]
            all_probes = flask.request.probes_network
            for probe in all_probes:
                try:
                    if selectedProbe == filter_network_interface(probe):
                        probes.append("%s.%s.grid5000.fr" % (probe.split(".")[1],probe.split(".")[0]))
                except:
                    continue
        nodes = probes
    else:
        probes = []
        for node in nodes:
            selectedProbe = site + '.' + node.split('.')[0]
            all_probes = flask.request.probes_power
            for probe in all_probes:
                try:
                    if selectedProbe == filter_network_interface(probe):
                        probes.append("%s.%s.grid5000.fr" % (probe.split(".")[1],probe.split(".")[0]))
                except:
                    continue
        nodes = probes
    try:
        started_at = job_properties['started_at']
    except KeyError:
        started_at = 'Undefined'
    try:
        stopped_at = job_properties['stopped_at']
    except KeyError:
        stopped_at = 'Undefined'
    return flask.jsonify({'job': int(job),
                          'started_at': started_at,
                          'stopped_at': stopped_at,
                          'nodes': nodes})


@blueprint.route('/zip/')
def send_zip():
    """Sends zip file."""
    probes = flask.request.args.get('probes', [])
    try:
        if probes:
            probes = probes.split(',')
        else:
            probes = []
        probes = [probe.encode('utf-8') for probe in probes]
    except:
        probes = []
    tmp_file = tempfile.NamedTemporaryFile(prefix="kwapi", suffix=".zip")
    zip_file = zipfile.ZipFile(tmp_file.name, 'w')
    metrics = ['power','network_in', 'network_out']
    scales = ['minute', 'hour', 'day', 'week', 'month', 'year']
    if len(probes) == 0:
        probes = flask.request.probes_network
    for metric in metrics:
        for probe in probes:
            try:
                rrd_files = live.get_rrds_from_name(probe, metric)
                if len(rrd_files) == 0:
                    # No RRD to store in zip
                    LOG.error("No RRD for %s, %s" % (metric, probe))
                    continue
                for i in range(len(rrd_files)):
                    zip_file.write(rrd_files[i], '/rrd/%s_%s_%d.rrd' %(metric, probe.replace(".","-"), i))
                for scale in scales:
                    # FIXME: Hack to chose metric
                    if metric == "power":
                        png_file = live.build_graph("energy",
                                            int(time.time()) - flask.request.scales[scale][0]['interval'],
                                            int(time.time()),
                                            probe,
                                            summary=False,
                                            zip_file=True)
                        zip_file.write(png_file, '/png/%s_%s_%s.png' % (metric, probe, scale))
                        os.unlink(png_file)
                    elif metric == "network_in":
                        png_file = live.build_graph("network",
                                            int(time.time()) - flask.request.scales[scale][0]['interval'],
                                            int(time.time()),
                                            probe,
                                            summary=False,
                                            zip_file=True)
                        zip_file.write(png_file, '/png/%s_%s_%s.png' % ("network", probe, scale))
                        os.unlink(png_file)
                    else:
                        continue
            except Exception as e:
                LOG.error("Fail to add %s: %s" % (probe, e))
                continue
    # Generate summary
    for scale in scales:
        try:
            png_file_energy = live.build_graph('energy',
                                               int(time.time()) - flask.request.scales[scale][0]['interval'],
                                               int(time.time()),
                                               probes,
                                               summary=True,
                                               zip_file=True)
            if png_file_energy:
                zip_file.write(png_file_energy, '/png/summary-energy-' + scale + '.png')
                os.unlink(png_file_energy)
        except Exception as e:
            LOG.error("Fail to add energy %s, %s: %s" % (probes, scale, e))
            continue
    for scale in scales:
        try:
            png_file_network = live.build_graph('network',
                                                int(time.time()) - flask.request.scales[scale][0]['interval'],
                                                int(time.time()),
                                                probes,
                                                summary=True,
                                                zip_file=True)
            if png_file_network:
                zip_file.write(png_file_network, '/png/summary-network-' + scale + '.png')
                os.unlink(png_file_network)
        except Exception as e:
            LOG.error("Fail to add network %s, %s: %s" % (probes, scale, e))
            continue
    return flask.send_file(tmp_file,
                           as_attachment=True,
                           attachment_filename='rrd.zip',
                           cache_timeout=0,
                           conditional=True)


@blueprint.route('/<metric>/summary-graph/<start>/<end>/')
def send_summary_graph(metric,start, end):
    """Sends summary graph."""
    probes_list = []
    if metric == 'energy':
        probes_list = flask.request.probes_power
    elif metric == 'network':
        probes_list = flask.request.probes_network
    else:
        flask.abort(404) 
    probes = flask.request.args.get('probes')
    if probes:
        probes = probes.split(',')
        probes = [probe.encode('utf-8') for probe in probes]
        for probe in probes:
            if probe not in probes_list:
                flask.abort(404)
    else:
        probes = list(probes_list)
    start = start.encode('utf-8')
    end = end.encode('utf-8')
    png_file = live.build_graph(metric, int(start), int(end), probes, True)
    if not png_file:
        flask.abort(404)
    tmp_file = tempfile.NamedTemporaryFile()
    shutil.copy2(png_file, tmp_file.name)
    if not png_file.endswith('summary-'+metric+'.png'):
        os.unlink(png_file)
    try:
        return flask.send_file(tmp_file,
                               mimetype='image/png',
                               cache_timeout=0,
                               conditional=True)
    except:
        flask.abort(404)


@blueprint.route('/<metric>/graph/<probe>/<start>/<end>/')
def send_probe_graph(metric, probe, start, end):
    """Sends graph."""
    probe = probe.encode('utf-8')
    start = start.encode('utf-8')
    end = end.encode('utf-8')
    png_file = live.build_graph(metric, int(start), int(end), probe, False)
    if not png_file:
        flask.abort(404)
    tmp_file = tempfile.NamedTemporaryFile()
    shutil.copy2(png_file, tmp_file.name)
    #os.unlink(png_file)
    #os.close(png_file)
    try:
        return flask.send_file(tmp_file, cache_timeout=0, conditional=True)
    except:
        flask.abort(404)
