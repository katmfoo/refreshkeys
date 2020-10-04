from setuptools import setup

setup(
    name='refreshkeys',
    version='1.0.0',
    url='https://github.com/pricheal/refreshkeys',
    author='Patrick Richeal',
    author_email='patrickricheal@gmail.com',
    description='Script to automatically refresh ssh/gpg key passphrases in keychain using 1password',
    license='MIT',
    packages=['refreshkeys'],
    entry_points={
        'console_scripts': [
            'refreshkeys=refreshkeys:main
        ]
    }
)
