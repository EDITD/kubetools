import re

from setuptools import find_packages, setup


# Regex matching pattern followed by 3 numerical values separated by '.'
pattern = re.compile(r'[0-9]+\.[0-9]+\.?[0-9]*\.?[a-z0-9]*')


def get_version():
    with open('CHANGELOG.md', 'r') as fn:
        while True:
            version = pattern.findall(fn.readline())
            if len(version) > 0:
                return ''.join(version[0])


if __name__ == '__main__':
    setup(
        version=get_version(),
        name='kubetools',
        description=(
            'Kubetools is a tool and processes for developing and deploying '
            'microservices to Kubernetes.'
        ),
        author='Devs @ EDITED',
        author_email='nick@edited.com',
        url='http://github.com/EDITD/kubetools',
        packages=find_packages(),
        entry_points={
            'console_scripts': (
                # kubetools client commands
                'kubetools=kubetools.cli.__main__:main',
                # ktd dev commands
                'ktd=kubetools.dev.__main__:main',
            ),
        },
        install_requires=(
            'click>=7,<8',
            'docker>=3,<5',
            'pyyaml>=3,<6',
            'requests>=2,<3',
            'pydash',
            'pyretry',
            'setuptools',
            'kubernetes',
            'tabulate<1',
        ),
        extras_require={
            'dev': (
                'ipdb',
            ),
        },
    )
