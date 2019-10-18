# WIP/Unreleased

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
