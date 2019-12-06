import click


class Build(object):
    '''
    Build is a stub class that encapsulates the context and namespace for
    a given build, as well as accepting log entries.

    The kubetools server provides it's own build class, which also handles things
    like aborting builds via Redis and keeps them saved in the database.
    '''

    def __init__(self, env, namespace):
        self.env = env
        self.namespace = namespace

    def log_info(self, text, extra_detail=None):
        '''
        Create BuildLog information.
        '''

        if extra_detail:
            text = f'{text}@{extra_detail}'

        click.echo(text)
