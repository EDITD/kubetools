from contextlib import contextmanager

import click


class Build(object):
    '''
    Build is a stub class that encapsulates the context and namespace for
    a given build, as well as accepting log entries.

    The kubetools server provides it's own build class, which also handles things
    like aborting builds via Redis and keeps them saved in the database.
    '''

    in_stage = False

    def __init__(self, env, namespace):
        self.env = env
        self.namespace = namespace

    def log_info(self, text, extra_detail=None, formatter=lambda s: s):
        '''
        Create BuildLog information.
        '''

        if extra_detail:
            text = f'{text}@{extra_detail}'

        if self.in_stage:
            text = f'    {text}'

        if formatter:
            text = formatter(text)

        click.echo(text)

    def log_warning(self, *args, **kwargs):
        kwargs['formatter'] = lambda s: click.style(s, 'yellow')
        self.log_info(*args, **kwargs)

    def log_error(self, *args, **kwargs):
        kwargs['formatter'] = lambda s: click.style(s, 'red')
        self.log_info(*args, **kwargs)

    @contextmanager
    def stage(self, stage_name):
        click.echo(f'--> {stage_name}')
        old_in_stage = self.in_stage
        self.in_stage = True
        yield
        self.in_stage = old_in_stage
        click.echo()
