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


class KubeAuthError(KubeError):
    type = 'auth'


# Local/dev errors
#

class KubeDevError(KubeCLIError):
    type = 'dev'


class KubeDevCommandError(KubeDevError):
    type = 'dev'
