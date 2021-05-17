# Changelog

### Unreleased

# v13.0.0

- Translate k8s-style `command`/`args` options to docker[-compose]-style `entrypoint`/`command`
  
  This is breaking backwards compatibility for any project using `entrypoint`/`command` options in a `dev` section.
  These need to be renamed resp. `command`/`args` to be picked up. The bright side of this is that these cases
  will now only require 1 copy of the options when the same values were just repeated under `dev` to get them to
  work with `ktd` (`docker-compose`)
  
# v12.2.2

- Ignore pods with no owner metadata when restarting a service

# v12.2.1

- Fix call to check if service exists

# v12.2.0

- Remove Kubernetes jobs after they complete successfully

# v12.1.0

- Allow to run upgrades and tests on any container using a containerContext. Especially allows containers that use a released image rather than a Dockerfile

# v12.0.3

- Ensure docker compose configs are always generated relative to the kubetools config file
- Fix use of `--debug` when using `ktd`

# v12.0.2

- Fix issue when creating new deployments alongside existing ones
- Fix `kubetools restart`

# v12.0.1

- Fix cleanup failure in removing namespaces which contain replica sets

# v12.0

Breaking note: this change passes all non Kubetools specific container config through to the generated K8s container spec. Any invalid/unused data would have previously been ignored will now be passed to K8s and throw an error.

- Pass any non-Kubetools specific container config through to K8s container spec
- Implicitly create target namespace if it does not exist
- The `--cleanup` flag will now remove the target namespace if empty
- Add `-f` / `--force` argument to `kubetools restart`
- Add `-e KEY=VALUE` flag to inject environment variables when using `kubetools deploy`
- Replace `yaml.load` with `yaml.safe_load` to avoid CLI warning
- Fix issues with listing objects in `kubetools restart`
- Fix the test condition for upgrades


# v11.1.1

- Fix `-f` / `--file` handling NoneType attribute error (introduced in v11.1)

# v11.1

- Add `-f`/`--file` argument to specify custom `kubetools.yml` file location for `kubetools deploy` and `kubetools config`
- Add `--ignore-git-changes` argument to skip git check for uncommitted files for `kubetools deploy`

# v11.0

This release follows a major overhaul of Kubetools - most notably moving all of the server/build logic down into this library (to deprecate/remove the server). The `kubetools` command can now deploy direct to Kubernetes.

- **Migration to client-only** (no more server), meaning new/changed commands:
    + `kubetools deploy <namespace> <app_path> [<app_path>...]`
    + `kubetools remove <namespace> [<app>...]`
    + `kubetools restart <namespace> <app>`
    + `kubeotols cleanup <namespace>`
    + `kubetools show <namespace> [<app>]`
    + Commands removed:
        * `kubetools wait`
        * `kubetools list *`
        * `kubetools job *`
- **Remove Python 2 support**
- Uses `kubeconfig` and Kubernetes contexts
- Correctly uses Kubernetes deployment objects for proper rolling updates
    + This also adds rollback compatability
- Improved replica control in `kubetools.yml`:
    + `deployments.NAME.minReplicas` (max exists already)
    + `deployments.NAME.replicaMultiplier`
- Support deployment strategy in `kubetools.yml`:
    + `deployments.NAME.updateStrategy` -> K8s `Deployment.spec.strategy`
- Add `--annotation` argument to `kubetools deploy`
- Add `--shell` argument to `ktd enter`


# v10.2
- Always ensure deployment names start with the project name

# v10.1.1
- Fix Python 2 compatability (broken in v10)

# v10.1
- Add `KTD_ENV` environment variable in `docker-compose` dev backend
- Print out all injected environment variables in `docker-compose` dev backend
- Replace `envars` with `envvars` everywhere (w/backwards compatability)

# v10.0
- Fix issue where stdout from a kubetools dev exception would not be formatted properly
- Add "dev backends" support for future work (alternatives to `docker-compose`)
- Add kubernetes config generation from the kubetools server
  * adds `kubetools configs` command to generate/view them by hand


# v9.1.1
- Add ability to define number of retries on readinessProbe

# v9.1
- Add `ktd restart` command
- Search for `kubetools.yml` "up" the directory tree, similar to `.git`

# v9.0.3
- Bump min click version to 7

# v9.0.2
- Fix clashes between two projects starting with the same name

# v9.0.1
- Version bump for pypi release

# v9.0.0
- Initial public release
