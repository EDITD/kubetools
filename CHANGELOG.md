# v11.0.dev3

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
- Support deployment strategy in `kubetools.yml`:
    + `deployments.NAME.updateStrategy` -> K8s `Deployment.spec.strategy`
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
