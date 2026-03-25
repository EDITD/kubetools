import re
from os import path

from setuptools import find_packages, setup


# Regex matching pattern followed by 3 numerical values separated by '.'
pattern = re.compile(r'# v(?P<version>[0-9]+\.[0-9]+(\.[0-9]+(\.[a-z0-9]+)?)?)')


def get_version():
    with open('CHANGELOG.md', 'r') as fn:
        for line in fn.readlines():
            match = pattern.fullmatch(line.strip())
            if match:
                return ''.join(match.group('version'))
    raise RuntimeError('No version found in CHANGELOG.md')


base_dir = path.abspath(path.dirname(__file__))


def get_readme_content():
    readme_file = path.join(base_dir, 'README.md')
    with open(readme_file, 'r') as f:
        return f.read()


if __name__ == '__main__':
    setup(
        version=get_version(),
        name='kubetools',
        description=(
            'Kubetools is a tool and processes for developing and deploying '
            'microservices to Kubernetes.'
        ),
        author='EDITED devs',
        author_email='dev@edited.com',
        url='http://github.com/EDITD/kubetools',
        long_description=get_readme_content(),
        long_description_content_type='text/markdown',
        packages=find_packages(),
        entry_points={
            'console_scripts': (
                # kubetools client commands
                'kubetools=kubetools.cli.__main__:main',
                # ktd dev commands
                'ktd=kubetools.dev.__main__:main',
            ),
        },
        python_requires='>=3.6',
        install_requires=(
            'click>=7,<8',
            'docker>=3,<5',
            'pyyaml>=3,<6',
            'requests>=2,<2.29.0',  # https://github.com/docker/docker-py/issues/3113
            'pyretry',
            'setuptools',
            # To support CronJob api versions 'batch/v1beta1' & 'batch/v1'
            'kubernetes>=21.7.0,<25.0.0',
            'tabulate<1',
            # compose v2 has broken container naming
            'docker-compose<2',
        ),
        extras_require={
            'dev': (
                'ipdb',
                'pytest~=6.0',
                'pytest-cov~=2.10',
                'flake8',
                'flake8-import-order',
                'flake8-commas',
            ),
        },
        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Environment :: Console',
            'Intended Audience :: Developers',
            'Intended Audience :: Information Technology',
            'License :: OSI Approved :: MIT License',
            'Operating System :: POSIX',
            'Programming Language :: Python',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
            'Programming Language :: Python :: 3.9',
            'Programming Language :: Python :: 3.10',
            'Programming Language :: Python :: 3.11',
            'Programming Language :: Python :: 3.12',
            'Topic :: Software Development :: Build Tools',
            'Topic :: Software Development :: Testing',
            'Topic :: System :: Software Distribution',
        ],
    )
