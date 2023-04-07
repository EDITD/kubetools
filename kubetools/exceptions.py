class KubeError(Exception):
    type = 'generic'


# Config errors
#

class KubeConfigError(KubeError):
    type = 'config'


# Client/server errors
#

class KubeClientError(KubeError):
    type = 'client'


class KubeServerError(KubeError):
    type = 'server'


class KubeCLIError(KubeError):
    type = 'cli'


# Build errors
#

class KubeBuildError(KubeError):
    type = 'build'


# Local/dev errors
#

class KubeDevError(KubeCLIError):
    type = 'dev'


class KubeDevCommandError(KubeDevError):
    type = 'dev'
