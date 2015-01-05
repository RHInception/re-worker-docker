# -*- coding: utf-8 -*-
# Copyright © 2014 SEE AUTHORS FILE
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
Docker worker.
"""

from reworker.worker import Worker
from docker import Client


class DockerWorkerError(Exception):
    """
    Base exception class for DockerWorker errors.
    """
    pass


class DockerWorker(Worker):
    """
    Worker which provides basic functionality for Docker.
    """

    #: allowed subcommands
    subcommands = (
        'StopContainer', 'RemoveContainer', 'RemoveImage',
        'PullImage', 'CreateContainer', 'StartContainer')
    dynamic = []

    # Subcommand methods
    def stop_container(self, body, corr_id, output):
        """
        Stops a single container.

        Parameters:

        * body: The message body structure
        * corr_id: The correlation id of the message
        * output: The output object back to the user
        """
        # Get needed variables
        params = body.get('parameters', {})

        try:
            server_name = params['server_name']
            container_name = params['container_name']
            client = docker.Client(base_url = server_name,version = self._config['version'])
            client.stop(container_name, timeout=10)

        except KeyError, ke:
            output.error(
                'Unable to stop container %s because of missing input %s' % (
                    params.get('container_name', 'IMAGE_NOT_GIVEN'), ke))
            raise DockerWorkerError('Missing input %s' % ke)
        except error.APIerror, ae:
            self.app_logger.warn(
                'Unable to stop %s. Error: %s' % ( params.get('container_name', ae)))
            raise DockerWorkerError(
                'No such container is running currently.' )
        except requests.exceptions.ConnectionError, ce:
            self.app_logger.warn(
                'Unable to connect to %s. Error: %s' % ( params.get('server_name', ce)))
            raise DockerWorkerError(
                'Could not connect to the requested Docker Host' )

    def remove_container(self, body, corr_id, output):
        """
        Remove a single container.

        Parameters:

        * body: The message body structure
        * corr_id: The correlation id of the message
        * output: The output object back to the user
        """
        # Get needed variables
        params = body.get('parameters', {})

        try:
            server_name = params['server_name']
            container_name = params['container_name']
            client = docker.Client(base_url = server_name,version = self._config['version'])
            client.remove(container_name)

        except KeyError, ke:
            output.error(
                'Unable to remove container %s because of missing input %s' % (
                    params.get ('container_name', 'IMAGE_NOT_GIVEN'), ke))
            raise DockerWorkerError('Missing input %s' % ke)
        except error.APIerror, ae:
            self.app_logger.warn(
                'Unable to remove %s. Error: %s' % ( params.get ('container_name', ae)))
            raise DockerWorkerError(
                'No such container exists on the server.' )
        except requests.exceptions.ConnectionError, ce:
            self.app_logger.warn(
                'Unable to connect to %s. Error: %s' % ( params.get ('server_name', ce)))
            raise DockerWorkerError(
                'Could not connect to the requested Docker Host' )

    def remove_image(self, body, corr_id, output):
        """
        Remove a single Image.

        Parameters:

        * body: The message body structure
        * corr_id: The correlation id of the message
        * output: The output object back to the user
        """
        # Get needed variables
        params = body.get('parameters', {})

        try:
            server_name = params['server_name']
            image_name = params['image_name']
            client = docker.Client(base_url = server_name,version = self._config['version'])
            client.remove(image_name)

        except KeyError, ke:
            output.error(
                'Unable to remove image %s because of missing input %s' % (
                    params.get ('image_name', 'IMAGE_NOT_GIVEN'), ke))
            raise DockerWorkerError('Missing input %s' % ke)
        except error.APIerror, ae:
            self.app_logger.warn(
                'Unable to remove %s. Error: %s' % ( params.get ('image_name', ae)))
            raise DockerWorkerError(
                'No such image exists on the server.' )
        except requests.exceptions.ConnectionError, ce:
            self.app_logger.warn(
                'Unable to connect to %s. Error: %s' % ( params.get ('server_name', ce)))
            raise DockerWorkerError(
                'Could not connect to the requested Docker Host' )

    def pull_image(self, body, corr_id, output):
        """
        Pull a single Image.

        Parameters:

        * body: The message body structure
        * corr_id: The correlation id of the message
        * output: The output object back to the user
        """
        # Get needed variables
        params = body.get('parameters', {})

        try:
            server_name = params['server_name']
            image_name = params['image_name']
            insecure_registry = params['secure']
            client = docker.Client(base_url = server_name,version = self._config['version'])
            client.pull(image_name, insecure_registry = secure)

        except KeyError, ke:
            output.error(
                'Unable to pull image %s because of missing input %s' % (
                    params.get ('image_name', 'IMAGE_NOT_GIVEN'), ke))
            raise DockerWorkerError('Missing input %s' % ke)
        #### Need to figure out how to raise fail on not find
        except requests.exceptions.ConnectionError, ce:
            self.app_logger.warn(
                'Unable to connect to %s. Error: %s' % ( params.get ('server_name', ce)))
            raise DockerWorkerError(
                'Could not connect to the requested Docker Host' )


    def create_container(self, body, corr_id, output):
        """
        Create a single container.

        Parameters:

        * body: The message body structure
        * corr_id: The correlation id of the message
        * output: The output object back to the user
        """
        # Get needed variables
        params = body.get('parameters', {})

        try:
            server_name = params['server_name']
            image_name = params['image_name']
            container_name = params['container_name']
            container_command = params['container_command']
            container_hostname = params['container_hostname']
            container_port = params['container_port']
            client = docker.Client(base_url = server_name,version = self._config['version'])
            client.create_container(image_name, name = container_name, command = container_command, hostname = container_hostname, ports = [container_port])

        except KeyError, ke:
            output.error(
                'Unable to create container %s because of missing input %s' % (
                    params.get ('container_name', 'IMAGE_NOT_GIVEN'), ke))
            raise DockerWorkerError('Missing input %s' % ke)
        except error.APIerror, ae:
            self.app_logger.warn(
                'Unable to remove %s. Error: %s' % ( params.get ('image_name', ae)))
            raise DockerWorkerError(
                'No such image exists on the server.' )
        except requests.exceptions.ConnectionError, ce:
            self.app_logger.warn(
                'Unable to connect to %s. Error: %s' % ( params.get ('server_name', ce)))
            raise DockerWorkerError(
                'Could not connect to the requested Docker Host' )

    def start_container(self, body, corr_id, output):
        """
        Start a single container.

        Parameters:

        * body: The message body structure
        * corr_id: The correlation id of the message
        * output: The output object back to the user
        """
        # Get needed variables
        params = body.get('parameters', {})

        try:
            server_name = params['server_name']
            container_name = params['container_name']
            container_binds = params['container_binds']
            port_bindings = params['port_bindings']
            client = docker.Client(base_url=server_name,version=self._config['version'])
            client.start_container(container=container_name, container_binds = container_binds, port_bindings = [port_bindings])

        except KeyError, ke:
            output.error(
                'Unable to start container %s because of missing input %s' % (
                    params.get ('container_name', 'IMAGE_NOT_GIVEN'), ke))
            raise DockerWorkerError('Missing input %s' % ke)
        except requests.exceptions.ConnectionError, ce:
            self.app_logger.warn(
                'Unable to connect to %s. Error: %s' % ( params.get ('server_name', ce)))
            raise DockerWorkerError(
                'Could not connect to the requested Docker Host' )
        except error.APIerror, ae:
            self.app_logger.warn(
                'Unable to start %s. Error: %s' % ( params.get ('container_name', ae)))
            raise DockerWorkerError(
                'No such container exists' )

    def process(self, channel, basic_deliver, properties, body, output):
        """
        Processes DockerWorker requests from the bus.

        *Keys Requires*:
            * subcommand: the subcommand to execute.
        """
        # Ack the original message
        self.ack(basic_deliver)
        corr_id = str(properties.correlation_id)
        # Notify we are starting
        self.send(
            properties.reply_to, corr_id, {'status': 'started'}, exchange='')

        try:
            try:
                subcommand = str(body['parameters']['subcommand'])
                if subcommand not in self.subcommands:
                    raise KeyError()
            except KeyError:
                raise DockerWorkerError(
                    'No valid subcommand given. Nothing to do!')

            cmd_method = None
            subcommand
            if subcommand == 'StopContainer':
                cmd_method = self.stop_container
            elif subcommand == 'RemoveContainer':
                cmd_method = self.remove_container
            elif subcommand == 'RemoveImage':
                cmd_method = self.remove_image
            elif subcommand == 'PullImage':
                cmd_method = self.pull_image
            elif subcommand == 'CreateContainer':
                cmd_method = self.create_container
            elif subcommand == 'StartContainer':
                cmd_method = self.start_container
            else:
                self.app_logger.warn(
                    'Could not find the implementation of subcommand %s' % (
                        subcommand))
                raise DockerWorkerError('No subcommand implementation')

            result = cmd_method(body, corr_id, output)
            # Send results back
            self.send(
                properties.reply_to,
                corr_id,
                {'status': 'completed', 'data': result},
                exchange=''
            )
            # Notify on result. Not required but nice to do.
            self.notify(
                'DockerWorker Executed Successfully',
                'DockerWorker successfully executed %s. See logs.' % (
                    subcommand),
                'completed',
                corr_id)

            # Send out responses
            self.app_logger.info(
                'DockerWorker successfully executed %s for '
                'correlation_id %s. See logs.' % (
                    subcommand, corr_id))

        except DockerWorkerError, fwe:
            # If a DockerWorkerError happens send a failure log it.
            self.app_logger.error('Failure: %s' % fwe)
            self.send(
                properties.reply_to,
                corr_id,
                {'status': 'failed'},
                exchange=''
            )
            self.notify(
                'DockerWorker Failed',
                str(fwe),
                'failed',
                corr_id)
            output.error(str(fwe))


def main():  # pragma: no cover
    from reworker.worker import runner
    runner(DockerWorker)


if __name__ == '__main__':  # pragma nocover
    main()
