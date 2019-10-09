# Kubetools Client
# File: kubetools/cli/lists.py
# Desc:

import click


from kubetools_client.cli import cli_bootstrap


@cli_bootstrap.group(help_priority=2)
def job():
    '''
    Manage Kubernetes jobs.
    '''


@job.command()
@click.argument('namespace')
@click.argument('job_id')
@click.pass_obj
def abort(client, namespace, job_id):
    if client.abort_job(namespace, job_id):
        click.echo('--> Job aborted: {0}/{1}'.format(
            namespace,
            click.style(job_id, bold=True),
        ))
    else:
        click.echo(click.style('Failed to abort job!', 'red'))


@job.command()
@click.argument('namespace')
@click.argument('job_id')
@click.pass_obj
def delete(client, namespace, job_id):
    if client.delete_job(namespace, job_id):
        click.echo('--> Job deleted: {0}/{1}'.format(
            namespace,
            click.style(job_id, bold=True),
        ))
    else:
        click.echo(click.style('Failed to delete job!', 'red'))
