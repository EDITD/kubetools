def make_secret_volume_config(name, secret):
    volume_data = {
        'name': name,
        'csi': {
            'driver': 'secrets-store.csi.k8s.io',
            'readOnly': True,
            'volumeAttributes': {
                'secretProviderClass': secret['secretProviderClass'],
            },
        },
    }

    return volume_data
