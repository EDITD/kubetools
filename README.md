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

## Developing

Install the package in editable mode, with the dev extras:

```sh
pip install -e .[dev]
```
