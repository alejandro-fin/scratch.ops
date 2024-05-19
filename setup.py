# Ideally 100% of the work should be handled by setup.cfg, so this function should "do nothing". Only reason this setup.py
# file is needed is to enable editable installs. Potentially it might also be needed to create a Conda package
# (as opposed to just a PyPI package)
import setuptools

setuptools.setup()
