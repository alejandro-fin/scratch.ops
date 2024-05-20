import os                                                           as _os
import re                                                           as _re

from conway.application.application                                 import Application
from conway.observability.logger                                    import Logger
from conway.util.path_utils                                         import PathUtils

from conway_ops.onboarding.user_profile                             import UserProfile
from conway_ops.util.git_branches                                   import GitBranches

class NB_Logger(Logger):
    '''
    This is a mock logger, needed in order to run conway services in a Jupyter notebook.

    Specifically, it is needed by the :class:`SDLC_NB_Application`. Please refer to its
    documentation as to why these mock classes are needed in order to run conway services.
    '''


class Scratch_NB_Application(Application):

    '''
    This is a mock application, which is needed in order to run the scratch library methods in a
    notebook.


    This is needed because the :class:`scratch` requires that any business logic be run under
    the context of a global :class:`Application` object, which is normally the case for real applications, or 
    for tests of real applications.

    So in order to run notebooks (whether to manage repo lifecycles, seed scenarios or just troubleshooting)
    without a real application, we use this (mock) Application as a global context.

    Hence this class, which is initialized in ``notebooks.sdlc_nb_utils.py``

    :param str profile_name: optional parameter to determine which user profile to use. By default it is
                null, which means that this class will try to infer the profile name from the current directory.
    :param str project_name: optional parameter to determine which user project to use. By default it is
                null, which means that this class will try to infer the profile name from the current directory.
    '''
    def __init__(self, profile_name=None, project_name=None):

        APP_NAME                                        = "Scratch_NB_App"

        logger                                          = NB_Logger(activation_level=Logger.LEVEL_INFO)
        
        # __file__ is something like
        #
        #       /home/alex/consultant1@CCL/dev/scratch_fork/scratch.ops/src/nb_apps/sdlc_nb_application.py
        #
        # In that example, the config folder for the Scratch_NB_Application would be in 
        #
        #       /home/alex/consultant1@CCL/dev/scratch_fork/scratch.ops/config
        #
        # So we can get that folder by navigating from __file__ the right number of parent directories up
        #
        config_path                                     = PathUtils().n_directories_up(__file__, 2) + "/config"

        super().__init__(app_name=APP_NAME, config_path=config_path, logger=logger)

    
