from setuptools import setup

from timebook import get_version

setup(
    name='timebook',
    version=get_version(),
    url='https://github.com/imiric/timebook',
    description='track what you spend time on',
    author='Trevor Caira',
    author_email='trevor@caira.com',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Utilities',
    ],
    packages=['timebook'],
    install_requires=[
        'docopt==0.6.2',
    ],
    entry_points={'console_scripts': [
        't = timebook.cmdline:run_from_cmdline']},
)
