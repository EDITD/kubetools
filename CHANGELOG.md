# Changelog

### Unreleased

# v13.14.0
- Fix docker-compose conflict when kubetools commands are called without activating their venv
- Add Python 3.12 to supported versions, albeit without Flake8 because of CPython bug
- Upgrade GitHub actions workflow to deal with deprecation warnings

# v13.13.1
- Add nodeSelector config to kubetools file
- Fix bug where `config` command was not printing the actual `k8s` configs used by `deploy` because it did not take into account the kube-context, whether default or given with `--context`.

# v13.13.0
- Cython 3.0 release is preventing this package to be released. A constraint of `cython<3` needs to be added to install this
- Add ability to use secrets in "migration" jobs

# v13.12.1
- De-couple serviceAccountName and secrets

# v13.12.0
- Add support for docker build arguments

# v13.11.0
- Add support to specify SecretProviderClass
- Add support to specify ServiceAccount

# v13.10.0
- Add ability to provide a custom script to check the presence of the image on the target registry
- Re-work checking for CronJob API version compatibility against the target k8s cluster
- Fix crash where we could try to delete `default` namespace, which is forbidden by k8s
- Fix crash where we tried to delete a namespace that doesn't exist
- Fix crash trying to gather annotations from k8s resource that can't have any

# v13.9.6
- Fix default registry option to not override registry for images specified
  directly, so they keep using the docker server default registry (dockerhub)

# v13.9.5.1
- No functional change, this is just validating the change of CI to Github Actions

# v13.9.5
DO NOT USE: This has a bug fixed in v13.9.6
- Allow adding a default registry in command line instead of
  specifying the registry in kubetools.yml file.

# v13.9.4
- Added support job time to live

# v13.9.3
- Add support for CronJob api version `batch/v1beta1`

# v13.9.2
- Ensure Resources within Job containers are parsed correctly, optimise
passing resources through `job_spec`

# v13.9.1
- Allow jobs to specify Resources within Job spec

# v13.9.0
- Add support for creating CronJob objects in k8s
- Fix bug where 2 concurrent `ktd` commands could create a duplicated `dev` network
- Small optimisation for checking presence of image in registry

# v13.8.1
- Pin docker-compose as v2 breaks docker naming convention

# v13.8.0
- Allow customisation of naming in job configuration

# v13.7.5
- Ensure command format is correct for full command strings

# v13.7.4
- Avoid shell escaping full command strings

# v13.7.3
- Add option to cleanup command for cleaning up completed jobs

# v13.6.3
- Shell-escape command in run container entrypoint

# v13.6.2
- Only build/push images relevant to relevant container contexts during a deploy

# v13.6.1

- Convert timeout envvar to int

# v13.6.0

- Add envvar to set timeouts for waiting for k8s funcs to complete

# v13.5.1

- Fix defaulting of propagation_policy param in k8s api job deletion

# v13.5.0

- Update push command to allow additional tags for image

# v13.4.1

- Fix regression from 13.0.0 causing upgrades and tests to fail when using an image with an entrypoint, or specifying
  one with "command" in the config

# v13.4.0

- Expose propagation_policy param in k8s api job deletion

# v13.3.0

- Add cli command for building and pushing app images to docker repo

# v13.2.0

- Add function to kubernetes api to list running jobs

# v13.1.0

- Update kubernetes api create job with non-blocking option

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
