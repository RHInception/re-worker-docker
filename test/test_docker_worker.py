# Copyright (C) 2014 SEE AUTHORS FILE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
Unittests.
"""

import docker
import pika
import mock
import requests

from contextlib import nested

from . import TestCase

from replugin import dockerworker


MQ_CONF = {
    'server': '127.0.0.1',
    'port': 5672,
    'vhost': '/',
    'user': 'guest',
    'password': 'guest',
}


class TestDockerWorker(TestCase):

    def setUp(self):
        """
        Set up some reusable mocks.
        """
        TestCase.setUp(self)

        self.channel = mock.MagicMock('pika.spec.Channel')

        self.channel.basic_consume = mock.Mock('basic_consume')
        self.channel.basic_ack = mock.Mock('basic_ack')
        self.channel.basic_publish = mock.Mock('basic_publish')

        self.basic_deliver = mock.MagicMock()
        self.basic_deliver.delivery_tag = 123

        self.properties = mock.MagicMock(
            'pika.spec.BasicProperties',
            correlation_id=123,
            reply_to='me')

        self.logger = mock.MagicMock('logging.Logger').__call__()
        self.app_logger = mock.MagicMock('logging.Logger').__call__()
        self.connection = mock.MagicMock('pika.SelectConnection')

    def tearDown(self):
        """
        After every test.
        """
        TestCase.tearDown(self)
        self.channel.reset_mock()
        self.channel.basic_consume.reset_mock()
        self.channel.basic_ack.reset_mock()
        self.channel.basic_publish.reset_mock()

        self.basic_deliver.reset_mock()
        self.properties.reset_mock()

        self.logger.reset_mock()
        self.app_logger.reset_mock()
        self.connection.reset_mock()

    def test_bad_command(self):
        """
        If a bad command is sent the worker should fail.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')):

            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "this is not a thing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'

    def test_docker_stop_container(self):
        """
        Verify docker:StopContainer works like it should.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "StopContainer",
                    "server_name": "localhost",
                    "container_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.error.call_count, 0)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'completed')

            # The docker client should connect to the server given and use the
            # proper version number as defined in the configuration file
            _client.assert_called_once_with(
                base_url="localhost", version=worker._config['version'])
            # The docker client should call stop once with the container name
            # and a timeout of 10
            _client().stop.assert_called_once_with("testing", timeout=10)

    def test_docker_stop_container_missing_input(self):
        """
        Verify docker:StopContainer fails if not given the proper information.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            # Missing container_name
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "StopContainer",
                    "server_name": "localhost",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')
            self.assertEquals(_client.call_count, 0)
            self.assertEquals(_client().stop.call_count, 0)

            # Reset some mocks ...
            self.app_logger.reset_mock()
            _client.reset_mock()

            # Missing server_name
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "StopContainer",
                    "container_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')
            self.assertEquals(_client.call_count, 0)
            self.assertEquals(_client().stop.call_count, 0)


    def test_docker_stop_container_exception_failures(self):
        """
        Verify docker:StopContainer handles exceptions properly.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            # APIError
            _client.side_effect = docker.errors.APIError("TEST", mock.MagicMock(content='asd'))
            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "StopContainer",
                    "server_name": "localhost",
                    "container_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            self.assertEquals(self.app_logger.warn.call_count, 1)
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')

            # Reset some mocks ...
            self.app_logger.reset_mock()
            _client.reset_mock()

            # ConnectionError
            _client.side_effect = requests.exceptions.ConnectionError()
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "StopContainer",
                    "server_name": "localhost",
                    "container_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.warn.call_count, 1)
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')

    def test_docker_remove_container(self):
        """
        Verify docker:RemoveContainer works like it should.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "RemoveContainer",
                    "server_name": "localhost",
                    "container_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.error.call_count, 0)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'completed')

            # The docker client should connect to the server given and use the
            # proper version number as defined in the configuration file
            _client.assert_called_once_with(
                base_url="localhost", version=worker._config['version'])
            # The docker client should call remove the container name
            _client().remove_container.assert_called_once_with("testing")

    def test_docker_remove_container_missing_input(self):
        """
        Verify docker:RemoveContainer fails if not given the proper information.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            # Missing container_name
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "RemoveContainer",
                    "server_name": "localhost",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')
            self.assertEquals(_client.call_count, 0)
            self.assertEquals(_client().stop.call_count, 0)

            # Reset some mocks ...
            self.app_logger.reset_mock()
            _client.reset_mock()

            # Missing server_name
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "RemoveContainer",
                    "container_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')
            self.assertEquals(_client.call_count, 0)
            self.assertEquals(_client().stop.call_count, 0)


    def test_docker_remove_container_exception_failures(self):
        """
        Verify docker:RemoveContainer handles exceptions properly.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            # APIError
            _client.side_effect = docker.errors.APIError("TEST", mock.MagicMock(content='asd'))
            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "RemoveContainer",
                    "server_name": "localhost",
                    "container_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            self.assertEquals(self.app_logger.warn.call_count, 1)
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')

            # Reset some mocks ...
            self.app_logger.reset_mock()
            _client.reset_mock()

            # ConnectionError
            _client.side_effect = requests.exceptions.ConnectionError()
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "RemoveContainer",
                    "server_name": "localhost",
                    "container_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.warn.call_count, 1)
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')

    def test_docker_remove_image(self):
        """
        Verify docker:RemoveImage works like it should.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "RemoveImage",
                    "server_name": "localhost",
                    "image_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.error.call_count, 0)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'completed')

            # The docker client should connect to the server given and use the
            # proper version number as defined in the configuration file
            _client.assert_called_once_with(
                base_url="localhost", version=worker._config['version'])
            # The docker client should call remove the container name
            _client().remove_image.assert_called_once_with("testing")

    def test_docker_remove_image_missing_input(self):
        """
        Verify docker:RemoveImage fails if not given the proper information.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            # Missing container_name
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "RemoveImage",
                    "server_name": "localhost",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')
            self.assertEquals(_client.call_count, 0)
            self.assertEquals(_client().stop.call_count, 0)

            # Reset some mocks ...
            self.app_logger.reset_mock()
            _client.reset_mock()

            # Missing server_name
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "RemoveImage",
                    "container_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')
            self.assertEquals(_client.call_count, 0)
            self.assertEquals(_client().stop.call_count, 0)


    def test_docker_remove_image_exception_failures(self):
        """
        Verify docker:RemoveImage handles exceptions properly.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            # APIError
            _client.side_effect = docker.errors.APIError("TEST", mock.MagicMock(content='asd'))
            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "RemoveImage",
                    "server_name": "localhost",
                    "image_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            self.assertEquals(self.app_logger.warn.call_count, 1)
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')

            # Reset some mocks ...
            self.app_logger.reset_mock()
            _client.reset_mock()

            # ConnectionError
            _client.side_effect = requests.exceptions.ConnectionError()
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "RemoveImage",
                    "server_name": "localhost",
                    "image_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.warn.call_count, 1)
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')

    def test_docker_pull_image(self):
        """
        Verify docker:PullImage works like it should.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "PullImage",
                    "server_name": "localhost",
                    "image_name": "testing",
                    "insecure_registry": True,
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.error.call_count, 0)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'completed')

            # The docker client should connect to the server given and use the
            # proper version number as defined in the configuration file
            _client.assert_called_once_with(
                base_url="localhost", version=worker._config['version'])
            # The docker client should call pull to grab the new image
            print _client().call_count
            _client().pull.assert_called_once_with("testing", insecure_registry=True)

    def test_docker_pull_image_missing_input(self):
        """
        Verify docker:PullImage fails if not given the proper information.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            # Missing container_name
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "PullImage",
                    "server_name": "localhost",
                    "insecure_registry": True,
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')
            self.assertEquals(_client.call_count, 0)
            self.assertEquals(_client().stop.call_count, 0)

            # Reset some mocks ...
            self.app_logger.reset_mock()
            _client.reset_mock()

            # Missing server_name
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "PullImage",
                    "container_name": "testing",
                    "insecure_registry": True,
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')
            self.assertEquals(_client.call_count, 0)
            self.assertEquals(_client().stop.call_count, 0)

    def test_docker_pull_image_exception_failures(self):
        """
        Verify docker:PullImage handles exceptions properly.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            # APIError
            _client.side_effect = docker.errors.APIError("TEST", mock.MagicMock(content='asd'))
            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                   "command": "docker",
                    "subcommand": "PullImage",
                    "server_name": "localhost",
                    "image_name": "testing",
                    "insecure_registry": True,
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            self.assertEquals(self.app_logger.warn.call_count, 1)
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')

            # Reset some mocks ...
            self.app_logger.reset_mock()
            _client.reset_mock()

            # ConnectionError
            _client.side_effect = requests.exceptions.ConnectionError()
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "PullImage",
                    "server_name": "localhost",
                    "image_name": "testing",
                    "insecure_registry": True,
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.warn.call_count, 1)
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')

    def test_docker_create_container(self):
       """
       Verify docker:CreateContainer works like it should.
       """
       with nested(
               mock.patch('pika.SelectConnection'),
               mock.patch('replugin.dockerworker.DockerWorker.notify'),
               mock.patch('replugin.dockerworker.DockerWorker.send'),
               mock.patch('docker.Client')) as (_, _, _, _client):

           worker = dockerworker.DockerWorker(
               MQ_CONF,
               logger=self.app_logger,
               config_file='conf/example.json')

           worker._on_open(self.connection)
           worker._on_channel_open(self.channel)

           body = {
               "parameters": {
                   "command": "docker",
                   "subcommand": "CreateContainer",
                   "server_name": "localhost",
                   "image_name": "testing",
                   "container_command": "/bin/bash",
                   "container_hostname": "test.local",
                   "container_name": "testing-container",
                   "container_ports": "443",
               },
           }

           # Execute the call
           worker.process(
               self.channel,
               self.basic_deliver,
               self.properties,
               body,
               self.logger)

           # The worker should not have any error logs and should respond
           # with a completed
           self.assertEquals(self.app_logger.error.call_count, 0)
           self.assertEquals(worker.send.call_args[0][2]['status'], 'completed')

           # The docker client should connect to the server given and use the
           # proper version number as defined in the configuration file
           _client.assert_called_once_with(
               base_url="localhost", version=worker._config['version'])
           # The docker client should call for a container to be created
           _client().create_container.assert_called_once_with('testing', name='testing-container', command='/bin/bash', hostname='test.local', ports=['443'])

    def test_docker_create_container_missing_input(self):
        """
        Verify docker:CreateContainer fails if not given the proper information.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            # Missing container_name
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "CreateContainer",
                    "server_name": "localhost",
                    "container_command": "/bin/bash",
                    "container_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')
            self.assertEquals(_client.call_count, 0)
            self.assertEquals(_client().stop.call_count, 0)

            # Reset some mocks ...
            self.app_logger.reset_mock()
            _client.reset_mock()

            # Missing server_name
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "CreateContainer",
                    "image_name": "testing",
                    "container_command": "/bin/bash",
                    "container_name": "testing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')
            self.assertEquals(_client.call_count, 0)
            self.assertEquals(_client().stop.call_count, 0)


    def test_docker_create_container_exception_failures(self):
        """
        Verify docker:CreateContainer handles exceptions properly.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            # APIError
            _client.side_effect = docker.errors.APIError("TEST", mock.MagicMock(content='asd'))
            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "CreateContainer",
                    "server_name": "localhost",
                    "image_name": "testing",
                    "container_command": "/bin/bash",
                    "container_hostname": "test.local",
                    "container_name": "testing-container",
                    "container_ports": "443",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            self.assertEquals(self.app_logger.warn.call_count, 1)
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')

            # Reset some mocks ...
            self.app_logger.reset_mock()
            _client.reset_mock()

            # ConnectionError
            _client.side_effect = requests.exceptions.ConnectionError()
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "CreateContainer",
                    "server_name": "localhost",
                    "image_name": "testing",
                    "container_command": "/bin/bash",
                    "container_hostname": "test.local",
                    "container_name": "testing-container",
                    "container_ports": "443",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.warn.call_count, 1)
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')

    def test_docker_start_container(self):
        """
        Verify docker:StartContainer works like it should.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "StartContainer",
                    "server_name": "localhost",
                    "container_name": "testing",
                    "port_bindings": {443: ('0.0.0.0', 443)},
                    "container_binds": {'/test':'/test'},
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.error.call_count, 0)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'completed')

            # The docker client should connect to the server given and use the
            # proper version number as defined in the configuration file
            _client.assert_called_once_with(
                base_url="localhost", version=worker._config['version'])
            # The docker client should call for a container to be created
            _client().start_container.assert_called_once_with("testing", binds={'/test':'/test'}, port_bindings={443: ('0.0.0.0', 443)})

    def test_docker_start_container_missing_input(self):
        """
        Verify docker:StartContainer fails if not given the proper information.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            # Missing container_name
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "StartContainer",
                    "server_name": "localhost",
                    "port_bindings": {443: ('0.0.0.0', 443)},
                    "container_binds": {'/test':'/test'},
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')
            self.assertEquals(_client.call_count, 0)
            self.assertEquals(_client().stop.call_count, 0)

            # Reset some mocks ...
            self.app_logger.reset_mock()
            _client.reset_mock()

            # Missing server_name
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "StartContainer",
                    "container_name": "testing-container",
                    "port_bindings": {443: ('0.0.0.0', 5671)},
                    "container_binds": {'/test':'/test'},
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')
            self.assertEquals(_client.call_count, 0)
            self.assertEquals(_client().stop.call_count, 0)


    def test_docker_start_container_exception_failures(self):
        """
        Verify docker:StartContainer handles exceptions properly.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.dockerworker.DockerWorker.notify'),
                mock.patch('replugin.dockerworker.DockerWorker.send'),
                mock.patch('docker.Client')) as (_, _, _, _client):

            # APIError
            _client.side_effect = docker.errors.APIError("TEST", mock.MagicMock(content='asd'))
            worker = dockerworker.DockerWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "StartContainer",
                    "server_name": "localhost",
                    "container_name": "testing",
                    "port_bindings": {443: ('0.0.0.0', 5671)},
                    "container_binds": {'/test':'/test'},
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            self.assertEquals(self.app_logger.warn.call_count, 1)
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')

            # Reset some mocks ...
            self.app_logger.reset_mock()
            _client.reset_mock()

            # ConnectionError
            _client.side_effect = requests.exceptions.ConnectionError()
            body = {
                "parameters": {
                    "command": "docker",
                    "subcommand": "StartContainer",
                    "server_name": "localhost",
                    "container_name": "testing-container",
                    "port_bindings": {443: ('0.0.0.0', 443)},
                    "container_binds": {'/test':'/test'},
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            # The worker should not have any error logs and should respond
            # with a completed
            self.assertEquals(self.app_logger.warn.call_count, 1)
            self.assertEquals(self.app_logger.error.call_count, 1)
            self.assertEquals(worker.send.call_args[0][2]['status'], 'failed')
