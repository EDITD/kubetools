from kubetools_client.log import logger


def convert_legacy_kubetools_config(config, dev):
    config.setdefault('tests', [])
    config.setdefault('upgrades', [])

    config['deployments'] = {
        config['name']: {
            'containers': {},
        },
    }

    if 'buildContexts' in config:
        config['containerContexts'] = {}

        for key, data in config.pop('buildContexts').items():
            if 'preBuildCommands' in config:
                data['preBuildCommands'] = config.get('preBuildCommands')

            config['containerContexts'][key] = {
                'build': data,
            }

    # Sort out any top level upgrades
    for upgrade in config['upgrades']:
        if 'buildContext' in upgrade:
            upgrade['containerContext'] = upgrade.pop('buildContext')

    # Sort out top level containers into a single top level deployment
    #

    for key, data in config.pop('containers').items():
        if 'buildContext' in data:
            data['containerContext'] = data.pop('buildContext')

        if dev:
            # Apply any devOverrides
            overrides = data.pop('devOverrides', None)
            if overrides:
                data.update(overrides)

            # In the old config dev-only upgrades were defined in postUpCommands for
            # each container, but now we only want them to be upgrades.
            post_up_commands = data.pop('postUpCommands', None)

            if post_up_commands:
                # Filter out postUpCommands that already exist
                existing_upgrade_commands = set()
                for upgrade in config.get('upgrades', []):
                    existing_upgrade_commands.add(tuple(upgrade['command']))

                for command in post_up_commands:
                    if tuple(command) not in existing_upgrade_commands:
                        config['upgrades'].append({
                            'command': command,
                            'containerContext': data['containerContext'],
                        })

        if 'testCommands' in data:
            for command in data.pop('testCommands'):
                config['tests'].append({
                    'command': command,
                    'containerContext': data['containerContext'],
                })

        config['deployments'][config['name']]['containers'][key] = data

    # Sort out dependencies and dev dependencies
    #

    dependencies = config.pop('dependencies', {})

    if dev:
        dev_dependencies = config.pop('devDependencies', {})

        if dev_dependencies:
            # Remove any *matching* containers from the main app - because in old
            # Kubetools devDependencies with the same name would override.
            for key in dev_dependencies.keys():
                config['deployments'][config['name']]['containers'].pop(key, None)

            dependencies.update(dev_dependencies)

    config['dependencies'] = {}

    for key, data in dependencies.items():
        if 'buildContext' in data:
            data['containerContext'] = data.pop('buildContext')

        if 'servicePorts' in data:
            data['ports'] = data['servicePorts']

        config['dependencies'][key] = {
            'containers': {
                key: data,
            },
        }

    # Sort out singletons to be deployments w/maxReplicas=1
    #

    singletons = config.pop('singletons', {})
    for key, data in singletons.items():
        if 'buildContext' in data:
            data['containerContext'] = data.pop('buildContext')

        singleton = {
            'maxReplicas': 1,
            'containers': {
                key: data,
            },
        }

        namespaces = data.get('namespaces')
        if namespaces:
            singleton.setdefault('conditions', {})['namespaces'] = namespaces

        singleton_key = '{0}-{1}'.format(config['name'], key)
        config['deployments'][singleton_key] = singleton

    logger.warning('Converted legacy Kubetools config')
