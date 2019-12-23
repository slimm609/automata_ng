#!/bin/bash
python3 setup.py build
python3 setup.py sdist upload


#rm -rf build automata_ssh.egg-info/