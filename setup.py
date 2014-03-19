""" setup.py """
# pylint: disable=C0301

from distutils.core import setup

setup(
    name='stageportal',
    version='0.2',
    author='Vitaly Kuznetsov',
    author_email='vitty@redhat.com',
    packages=['stageportal'],
    scripts=['bin/stageportal'],
    license='COPYING',
    description='Python library and cli to work with stage portal.',
    long_description=open('README.md').read(),
    data_files = [('/etc', ['etc/stageportal.cfg'])],
    install_requires=[
        "requests",
        "rhsm",
    ],
    dependency_links=[
        "https://github.com/candlepin/python-rhsm/archive/python-rhsm-1.10.7-1.tar.gz#egg=rhsm-1.10.7"
    ],

    classifiers = [
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Programming Language :: Python'
    ],
)
