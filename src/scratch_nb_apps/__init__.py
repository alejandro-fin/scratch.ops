from conway.application.application                                 import Application
from scratch_nb_apps.scratch_nb_application                         import Scratch_NB_Application

# Start the global singleton that represents a (mock) application for the
# :class:`scratch`
#
if Application._singleton_app is None:
    Scratch_NB_Application()
