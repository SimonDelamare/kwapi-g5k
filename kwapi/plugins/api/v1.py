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

import flask
import socket
blueprint = flask.Blueprint('v1', __name__)


@blueprint.route('/')
def welcome():
    """Returns detailed information about this specific version of the API."""
    return 'Welcome to Kwapi!'


@blueprint.route('/probe-ids/')
def list_probes_ids():
    """Returns all known probes IDs."""
    message = {}
    response = None
    try:
        message['probe_ids'] = []
        for k in flask.request.collector.database.keys():
            all_probe_ids = flask.request.collector.database[k].keys()
            message['probe_ids'].extend(all_probe_ids)
        response = flask.jsonify(message)
        response.headers.add('Access-Control-Allow-Origin', '*')
    except:
        flask.abort(404)
    return response


@blueprint.route('/probes/')
def list_probes():
    """Returns all information about all known probes."""
    message = {'probes': flask.request.collector.database}
    response = flask.jsonify(message)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@blueprint.route('/probes/<probe>/')
def probe_info(probe):
    """Returns all information about this probe (id, timestamp, value, unit)"""
    message = {}
    try:
        for k in flask.request.collector.database.keys():
            message[k] = {}
            message[k][probe] = flask.request.collector.database[k][probe]
    except KeyError as e:
        flask.abort(404, e)
    response = flask.jsonify(message)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@blueprint.route('/probes/<probe>/<meter>/')
def probe_value(probe, meter):
    """Returns the probe meter value."""
    message = {}
    try:
        message[meter] = \
            {
                probe: flask.request.collector.database[meter][probe]
            }
    except KeyError as e:
        flask.abort(404, str(e))
    response = flask.jsonify(message)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response
