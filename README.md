![Build Status](https://github.com/EDITD/kubetools/actions/workflows/run_tests.yml/badge.svg?branch=master)
[![Pypi Version](https://img.shields.io/pypi/v/kubetools.svg)](https://pypi.org/project/kubetools/)
[![Python Versions](https://img.shields.io/pypi/pyversions/kubetools.svg)](https://pypi.org/project/kubetools/)

# Kubetools

Kubetools is a tool and processes for developing and deploying microservices to Kubernetes. Say that:

+ You have **a bunch of repositories, each containing one or more microservices**
+ You want to **deploy each of these microservices into one or more Kubernetes clusters**
+ You want a **single configuration file per project** (repository)

And you would like:

+ **Development setup should be near-instant** - and _not_ require specific K8s knowledge
+ **Deployment to production can be automated** - and integrated with existing CI tooling

Kubetools provides the tooling required to achieve this, by way of two CLI tools:

+ **`ktd`**: generates _100% local_ development environments using Docker/docker-compose
+ **`kubetools`**: deploys projects to Kubernetes, handling any changes/jobs as required

Both of these use a single configuration file, `kubetools.yml`, for example a basic `django` app:

```yaml
name: my-app

containerContexts:
  django_app:
    build:
      registry: my-registry.net
      dockerfile: Dockerfile
    dev:
      volumes:
        - ./:/opt/django_app

upgrades:
  - name: Upgrade database
    containerContext: django_app
    command: [./manage.py, migrate, --noinput]

tests:
  - name: Nosetests
    containerContext: django_app
    command: [./manage.py, test]

deployments:
  my-app-webserver:
    serviceAccountName: webserver
    secrets:
      secret-volume:
        mountPath: /mnt/secrets-store
        secretProviderClass: webserver-secrets
    containers:
      uwsgi:
        command: [uwsgi, --ini, /etc/uwsgi.conf]
        containerContext: django_app
        ports:
          - 80
        dev:
          command: [./manage.py, runserver, '0.0.0.0:80']

dependencies:
  mariadb:
    containers:
      mariadb:
        image: mariadb:v10.4.1

cronjobs:
  my-cronjob:
    batch-api-version: 'batch/v1beta1'  # Must add if k8s version < 1.21+
    schedule: "*/1 * * * *"
    concurrency_policy: "Replace"
    containers:
      hello:
        image: busybox
        command: [/bin/sh, -c, date; echo Hello from the Kubernetes cluster]
```

With this in your current directory, you can now:

```sh
# Bring up a local development environment using docker-compose
ktd up

# Deploy the project to a Kubernetes namespace
kubetools deploy my-namespace
```

## Installing

```sh
pip install kubetools
```

**NOTE**: Since Cython 3.0 was released, the installation of `kubetools` dependencies will fail
 due to compatibility issues between Cython 3 and PyYaml (see
 [this issue](https://github.com/yaml/pyyaml/issues/601)). This can be worked around for example
 with `pip` by using a "constraints" file containing `cython<3`.

## Configuration
Users can configure some aspects of `kubetools`. The configuration folder location depends on the
operating system of the user. See the
[Click documentation](https://click.palletsprojects.com/en/8.1.x/api/#click.get_app_dir)
to find the appropriate one for you. Note that we use the "POSIX" version (for example
`~/.kubetools/` on Unix systems).
* `kubetools.conf` contains key-value settings, see [`settings.py`](kubetools/settings.py) for the
  possible settings and their meaning.
* `scripts/` can contain scripts to be made available to `ktd script` command

## Developing

Install the package in editable mode, with the dev extras:

```sh
pip install -e .[dev]
```

## Local deployment testing

For deployment testing, you will need a kubernetes cluster and a docker registry. You can get both
easily using `minikube`:
```shell
minikube start --addons registry --insecure-registry ${MINIKUBE_IP}:5000
```
Then you can deploy to that environment:
```shell
kubetools --context minikube deploy --default-registry ${MINIKUBE_IP}:5000 default .
```

`MINIKUBE_IP` value can vary depending on your local environment. The easiest way to get the correct
value is to start minikube once then reset it:
```shell
minikube start
MINIKUBE_IP=$(minikube ip)
minikube delete
...
```

## Releasing (admins/maintainers only)
* Update [CHANGELOG](CHANGELOG.md) to add new version and document it
* In GitHub, create a new release
  * Title the release `v<version>` (for example `v1.2.3`)
  * Select to create a new tag `v<version>` against `master` branch
  * Copy changes in the release from `CHANGELOG.md` into the release description
  * [GitHub Actions](https://github.com/EDITD/kubetools/actions) will package the release and
    publish it to [Pypi](https://pypi.org/project/kubetools/)

## Mounting K8s Secrets
We assume that `ServiceAccount` and `SecretProviderClass` are already created (if needed), before deploying the project with kubetools.

## Docker build args
`kubetools` now supports passing values for `ARG` parameters used in Dockerfiles, using
`--build-args`. This has a couple of caveats though:
* it is NOT supported in `ktd`. A workaround for this is to use the default value of the `ARG`
  instruction.
* this doesn't affect the image tag pushed to the docker registry, which is based only on the git
  commit hash. This means that these arguments cannot be used to generate multiple images from the
  same Dockerfile. So their main usage should be to pass secrets that should not be recorded in the
  git repository but are needed at build time, to access external resources for example.
* these values could be recorded in the docker image layer history. To prevent leaking secrets, you
  should consider using multi-stage builds where the secrets are only used in a "builder" image.
