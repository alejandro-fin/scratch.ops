import os                                                           as _os

from conway.application.application                                 import Application

from conway_ops.notebook_client.notebook_utils                      import NotebookUtils


class Scratch_NB_Utils(NotebookUtils):

    '''
    '''
    def __init__(self):

        # __file__ is something like 
        #
        #        '/home/alex/consultant1@CCL/scratch_fork/scratch.ops/nb_apps/scratch_nb_utils.py'
        #
        # So to get the repo ("scratch.ops") we need to go 1 directories up.
        #
        directory                       = _os.path.dirname(__file__)

        for idx in range(1):
            directory                   = _os.path.dirname(directory)
        repo_directory                  = directory

        super().__init__(project_name="scratch", repo_directory=repo_directory)

        self._import_scratch_dependencies()

    def _import_scratch_dependencies(self):
        '''
        Imports common Scratch modules that are often needed in Scratch notebooks, and remembers them as attributes
        of self
        '''
        from scratch_ops.onboarding.scratch_repo_bundle             import ScratchRepoBundle

        self.ScratchRepoBundle                      = ScratchRepoBundle


