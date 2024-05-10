
from conway_ops.onboarding.repo_bundle         import RepoBundle, RepoInfo

class ScratchRepoBundle(RepoBundle):

    '''
    '''
    def __init__(self):
        PROJECT_NAME                                    = "scratch"
        super().__init__(PROJECT_NAME)

    def bundled_repos(self):
        '''
        :return: The names of the repos comprising this :class:`RepoBundle`.
        :rtype: List[str]
        '''
        repo_info_l                                     = super().bundled_repos()

        return repo_info_l
