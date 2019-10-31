from setuptools import setup, find_packages

setup(name='automata-ssh',
      version='1.0.0',
      description='A CLI application to create user accounts on Linux systems from Gitlab users/group information.',
      author='Brian Davis',
      author_email='slimm609@gmail.com',
      license='GPLv3',
      packages=find_packages(),
      url = "http://packages.python.org/automata-ssh",
      zip_safe=False,
      entry_points={
          'console_scripts': [
              'automata=automatagl.automatagl:main',
          ],
      },
      install_requires=[
          "certifi==2019.3.9",
          "chardet==3.0.4",
          "idna==2.8",
          "PyYAML",
          "requests==2.22.0",
          "urllib3==1.25.3",
          "boto3",
      ],
    )
