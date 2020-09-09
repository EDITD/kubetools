from .util import make_dns_safe_name


def make_namespace_config(
    name,
    labels=None,
    annotations=None,
):
    '''
    Builds a Kubernetes namespace configuration dict.
    '''

    labels = labels or {}
    annotations = annotations or {}

    # The actual namespace spec
    namespace = {
        'apiVersion': 'v1',
        'kind': 'Namespace',
        'metadata': {
            'name': make_dns_safe_name(name),
            'labels': labels,
            'annotations': annotations,
        },
    }

    return namespace
