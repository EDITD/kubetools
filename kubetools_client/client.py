import json

from time import sleep

import requests
from requests.exceptions import ConnectionError

from kubetools_client.exceptions import KubeAuthError, KubeClientError
from kubetools_client.log import logger
from kubetools_client.settings import get_settings


GET_METHODS = {
    'list_manifests': 'manifests',
    'list_apps_by_namespace': ('apps', 'namespace_apps'),
    'list_jobs_by_namespace': ('jobs', 'namespace_jobs'),
    'list_builds': 'builds',
    'list_environments': 'environments',
    'list_locks': 'locks',
}


class KubeClient(object):
    def __init__(
        self,
        host=None,
        port=None,
        api_version=None,
        kube_env=None,
        api_key=None,
    ):
        settings = get_settings()

        host = host or settings.KUBETOOLS_HOST
        port = port or settings.KUBETOOLS_PORT
        api_version = api_version or settings.KUBETOOLS_API_VERSION

        kube_env = kube_env or settings.DEFAULT_KUBE_ENV

        self.base_url = 'http://{0}:{1}/api/v{2}'.format(host, port, api_version)
        self.kube_env = kube_env
        self.host = host
        self.port = port

        # Setup a requests session with any authentication methods we have configured
        session = requests.session()

        if api_key:
            session.headers['Authorization'] = api_key
        elif settings.KUBETOOLS_SESSION:
            session.cookies['session'] = settings.KUBETOOLS_SESSION

        self.session = session

    def __getattr__(self, key):
        if key in GET_METHODS:
            url = data_key = GET_METHODS[key]

            if isinstance(url, tuple):
                url, data_key = url

            def wrapper(**kwargs):
                response = self._request('GET', url, params=kwargs)
                return response.get(data_key)

            return wrapper

    def _request(self, method, endpoint, **kwargs):
        request_map = {
            'GET': self.session.get,
            'POST': self.session.post,
            'DELETE': self.session.delete,
        }

        if method not in request_map:
            raise KubeClientError('Invalid request method: {0}'.format(method))

        method_func = request_map[method]
        endpoint = '{0}/{1}'.format(self.base_url, endpoint)

        # Pop and apply any env param
        params = kwargs.pop('params', {})
        if self.kube_env:
            params['kube-env'] = self.kube_env

        logger.debug('Making requests {0} {1} ({2})'.format(
            method, endpoint, kwargs,
        ))

        try:
            response = method_func(endpoint, params=params, **kwargs)

        except ConnectionError:
            raise KubeClientError(
                'Could not connect to kubetools API: {0}'.format(endpoint),
            )

        if response.status_code == 200:
            return response.json()
        else:
            # Get the JSON error if available
            try:
                data = response.json()
                content = '{0} {1}: {2}'.format(
                    data['status_code'],
                    data['error_name'],
                    data['error_message'],
                )

            # It really broke, no JSON returned!
            except Exception:
                content = 'Invalid API response: {0}: {1}'.format(
                    response, response.content,
                )

            if response.status_code == 403:
                raise KubeAuthError(content)
            raise KubeClientError(content)

    def _json_request(self, *args, **kwargs):
        kwargs['headers'] = {
            'Content-Type': 'application/json',
        }

        if 'data' in kwargs:
            kwargs['data'] = json.dumps(kwargs['data'])

        return self._request(*args, **kwargs)

    def get_build_view_url(self, build_hash):
        '''
        Returns the frontend build URL for a given build hash.
        '''

        return 'http://{0}:{1}/build/{2}'.format(self.host, self.port, build_hash)

    def get_build(self, build_hash):
        '''
        Gets the detail of a single build.

        Args:
            build_hash (str): the hash of the build to lookup

        Returns:
            build data
        '''

        response = self._request('GET', 'build/{0}'.format(build_hash))
        return response['build']

    def wait_for_build(
        self, build_hash,
        statuses=('SUCCESS', 'ERROR'),
        sleep_time=1,
        max_errors=300,
    ):
        '''
        Wait for a build to be complete.

        Args:
            build_hash (str): the hash of the build to wait for
            statuses (tuple/list): the acceptable statuses to stop waiting on
            sleep_time (int): time to sleep between checks for complection
            max_errors (int): number of API errors in a row before giving up \
            (and raising an exception)

        Returns:
            build data
        '''

        build = self.get_build(build_hash)
        n_errors = 0

        while build['status'] not in statuses:
            sleep(sleep_time)

            try:
                build = self.get_build(build_hash)
                n_errors = 0  # reset the error count

            except KubeClientError as e:
                logger.warning('API error waiting for build: {0}'.format(e))

                if n_errors >= 300:
                    raise

                n_errors += 1

        return build

    def create_build(self, build_spec):
        '''
        Creates/schedules a build in Kubetools.

        Args:
            build_spec (dict): list of dicts containing at least field "app" and \
            optionally "replicas" and "version" where version is a Git branch

        Returns:
            the build hash
        '''

        response = self._json_request(
            'POST', 'build',
            data=build_spec,
        )

        return response['hash']

    def abort_build(self, build_hash):
        '''
        Aborts a build in Kubetools.

        Args:
            build_hash (str): the hash of the build to abort

        Returns:
            the api version
        '''

        endpoint = 'build/{0}/abort'.format(build_hash)

        response = self._request(
            'POST', endpoint,
        )

        return response

    def create_deploy(self, deploy_spec, namespace=None):
        '''
        Creates/schedules a build & deploy in Kubetools.

        Args:
            deploy_spec (list): list of dicts containing the app/replicas/version
            namespace (str): optional namespace to deploy to
        '''

        response = self._json_request(
            'POST', 'deploy',
            data=deploy_spec,
            params={'namespace': namespace},
        )

        return response['hash']

    def create_run(self, run_spec, namespace=None):
        '''
        Creates/schedules a build & run in Kubetools.

        Args:
            run_spec (list): list of dicts containing the app/replicas/version
            namespace (str): optional namespace to run to
        '''

        response = self._json_request(
            'POST', 'run',
            data=run_spec,
            params={'namespace': namespace},
        )

        return response['hash']

    def create_upgrade(self, namespace, upgrade_spec=None):
        '''
        Creates/schedules an upgrade in Kubetools.

        Args:
            namespace (str): the namespace to perform the upgrade in
            upgrade_spec (list): as above, contains a list of app/version/replicas

        Returns:
            the build hash
        '''

        response = self._json_request(
            'POST', 'upgrade/{0}'.format(namespace),
            data=upgrade_spec,
        )

        return response['hash']

    def create_remove(self, namespace, remove_spec=None):
        '''
        Creates/schedules a remove in Kubetools.

        Args:
            namespace (str): the namespace to remove apps from
            remove_spec (list): as above, contains a list of apps

        Returns:
            the build hash
        '''

        response = self._json_request(
            'POST', 'remove/{0}'.format(namespace),
            data=remove_spec,
        )

        return response['hash']

    def create_restart(self, namespace, restart_spec=None):
        '''
        Creates/schedules a restart in Kubetools.

        Args:
            namespace (str): the namespace to restart apps from
            restart_spec (list): as above, contains a list of apps

        Returns:
            the build hash
        '''

        response = self._json_request(
            'POST', 'restart/{0}'.format(namespace),
            data=restart_spec,
        )

        return response['hash']

    def create_cleanup(self, namespace):
        '''
        Creates/schedules a cleanup in Kubetools.

        Args:
            namespace (str): the namespace to cleanup

        Returns:
            the build hash
        '''

        response = self._json_request(
            'POST',
            'cleanup/{0}'.format(namespace),
        )

        return response['hash']

    def abort_job(self, namespace, job_id):
        '''
        Aborts a running Kubernetes job.

        Args:
            namespace (str): the namespace the job is running in
            job_id (str): the ID of the job to abort

        Returns:
            boolean indicating success/failure
        '''

        response = self._json_request(
            'POST',
            'abort_job/{0}/{1}'.format(namespace, job_id),
        )

        return response['aborted']

    def delete_job(self, namespace, job_id):
        '''
        Deletes a running Kubernetes job.

        Args:
            namespace (str): the namespace the job is running in
            job_id (str): the ID of the job to delete

        Returns:
            boolean indicating success/failure
        '''

        response = self._json_request(
            'POST',
            'delete_job/{0}/{1}'.format(namespace, job_id),
        )

        return response['deleted']
