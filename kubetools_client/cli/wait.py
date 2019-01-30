# Kubetools Client
# File: kubetools/cli/wait.py
# Desc: helpers for the Kubetools command line interface

import sys

import click

from kubetools_client.cli import cli_bootstrap
from kubetools_client.cli.wait_util import wait_with_spinner


@cli_bootstrap.command()
@click.argument('build_hash')
@click.pass_obj
def wait(client, build_hash):
    '''
    Wait for a Kubetools build.
    '''

    click.echo('### Watching build: {0}'.format(
        click.style(build_hash, bold=True),
    ))
    wait_build(client, build_hash)


def wait_job(client, namespace, job_id):
    def check_job_status(previous_status):
        namespace_jobs = client.list_jobs_by_namespace(namespace=namespace)
        job = namespace_jobs[namespace][job_id]

        if (
            # Job completed the number of times we want?
            job['succeeded'] == job['completions']
            # Job has failed over X times?
            or job['failed'] >= job['backoffLimit']
        ):
            return

        return job['annotations'].get('description', 'Running job')

    wait_with_spinner(check_job_status)

    # Get the job again
    namespace_jobs = client.list_jobs_by_namespace(namespace=namespace)
    job = namespace_jobs[namespace][job_id]
    status = job['succeeded'] == job['completions']

    if status:
        click.echo('<-- Job complete, final status = {0}'.format(
            click.style('SUCCESS', 'green'),
        ))

    else:
        click.echo('<-- Job complete, final status = {0}'.format(
            click.style('ERROR', 'red'),
        ))

    if not status:
        sys.exit(1)


def wait_build(client, build_hash):
    '''
    CLI helper that waits for a build to complete while displaying a little spinner.
    '''

    def check_build_status(previous_status):
        build_data = client.get_build(build_hash)

        # If we're complete, just return nothing
        if build_data['status'] not in ('PENDING', 'RUNNING'):
            return

        status_text = build_data['status']
        if build_data['status_detail']:
            status_text = '{0}/{1}'.format(status_text, build_data['status_detail'])

        return status_text

    wait_with_spinner(check_build_status)

    # Get the build date
    build_data = client.get_build(build_hash)
    status = build_data['status']

    # We did it!
    if status == 'SUCCESS':
        click.echo('--> Namespace: {0}'.format(click.style(
            build_data['namespace'], bold=True,
        )))

        domains = build_data.get('domains')
        if domains:
            for app, domain in domains.items():
                click.echo('--> App: {0} should now be available @ {1}'.format(
                    app, click.style(domain, bold=True),
                ))

    elif status == 'ABORTED':
        click.echo('--> {0}'.format(
            click.style(
                'Aborted at stage: {0}'.format(build_data['status_detail']),
                'yellow',
            ),
        ))

    # Status should be ERROR, but any non-success here is a fail
    else:
        click.echo('--> {0}'.format(
            click.style(
                'Error at stage: {0}'.format(build_data['status_detail']),
                'red',
            ),
        ))
        click.echo()
        click.echo('--------ERROR START--------')
        click.echo(click.style(build_data.get('error', 'Unknown error'), 'yellow'))
        click.echo('---------ERROR END---------')

    if status == 'SUCCESS':
        formatted_status = click.style('SUCCESS', 'green')
    elif status == 'ABORTED':
        formatted_status = click.style('ABORTED', 'yellow')
    else:
        formatted_status = click.style('ERROR', 'red')

    click.echo('<-- Build complete, final status = {0}'.format(formatted_status))

    if status == 'ABORTED':
        sys.exit(1)

    elif status != 'SUCCESS':
        sys.exit(2)
