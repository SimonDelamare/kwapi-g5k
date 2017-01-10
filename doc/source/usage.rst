..
      Copyright 2017 Clement Parisot (Inria)

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

=====
Usage
=====

Install Kwapi on your site
==========================

See *Installing Kwapi from source* to know how to install Kwapi.

Configuration
=============

.. warning:: Configuration files are only read once when the plugin/driver is started. You have to restart the plugin to load a new configuration.

Configure the drivers
---------------------

See the *Configuration* section for specific information on each driver configuration. If you are on Grid'5000 you can use the specific *kwapi-g5k-conf* tool to generate the configuration from the Grid'5000 API.

Configure the plugins
---------------------

Some plugins have specific options that you can configure (the size of HDF5 files for example). You can retrieve those options in the specific *<plugin_name>.conf* of Kwapi.

Choose which drivers/plugins to start
=====================================

By using the *daemon.conf* configuration file, you can specify which driver you want to run. By default (empty file), no Kwapi driver or plugin will run at all. They will be launch in the order defined in the file. 

Launch Kwapi
============

Start the system service to see Kwapi in action. You can check Kwapi status with the system command like an usual service *service kwapi status*.

Debug Kwapi execution
=====================

By default, all logs go to */var/log/kwapi/*. The file *kwapi.log* contains errors on kwapi service or errors that are not catch in drivers or plugins. There is 1 log file per driver/service + 1 log file for dedicated scripts (kwapi-g5k-conf and kwapi-g5k-check).

* HDF5 are quite big. Be sure to have sufficient space for them.
* Check that user kwapi have access to databases and log files under */var/lib/kwapi* and */var/log/kwapi*.
* A chunk size has been defined to limit stress of disk access introduced by HDF5 plugin. You can tune its value if you have problems with disk access.

