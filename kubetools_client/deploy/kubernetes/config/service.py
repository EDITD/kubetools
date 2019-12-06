from .util import make_dns_safe_name


def make_service_config(
    name, ports,
    node_port=True,
    labels=None,
    annotations=None,
):
    '''
    Builds a Kubernetes service configuration dict.
    '''

    labels = labels or {}
    annotations = annotations or {}

    # Build our ports list
    service_ports = []
    for port in ports:
        # Accept port dicts w/protocol/name/etc
        if isinstance(port, dict):
            # Default targetPort to same as port
            if 'targetPort' not in port:
                port['targetPort'] = port['port']

            service_ports.append(port)

        # And accept plain numbers
        else:
            service_ports.append({
                'port': port,
                'targetPort': port,
            })

    # The actual service spec
    service = {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {
            'name': make_dns_safe_name(name),
            'labels': labels,
            'annotations': annotations,
        },
        'spec': {
            'selector': labels,
            'ports': service_ports,
        },
    }

    if node_port:
        service['spec']['type'] = 'NodePort'

    return service
