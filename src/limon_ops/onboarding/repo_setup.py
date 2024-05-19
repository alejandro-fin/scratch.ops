import asyncio

from git                                                            import Repo

#from conway.application.application                                 import Application

from conway.observability.logger                                    import Logger
from conway.util.profiler                                           import Profiler
from conway.util.secrets                                            import Secrets

from conway_ops.onboarding.user_profile                             import UserProfile
from limon_ops.util.git_local_client                                import GitLocalClient


class RepoSetup():

    '''
    Class to support creation of a local development environment for a user's profile.

    The services of this class pre-suppose that the user's profile has access to one or more projects
    in GitHub, each of which consist of one or more repos.

    It also pre-supposes that the caller has access to user profile information.

    This class allows the user to clone such repos into a local folder of the user's choice, and to configure
    the local GIT repository as per Conway standards pased on the profile configuration. Specifically:

    * Creation of local branch based on the profile
    * Configure the local GIT repo's user and e-mail
    * Configure Beyond Compare as a diff and merge tool, invoked from WSL but running in Windows

    :param str sdlc_root: folder in the local file system under which CCL SDLC profiles and tools exist.
    :param str profile_name: name of the user profile for which repos should be setup.
    '''
    def __init__(self, sdlc_root, profile_name):

        self.sdlc_root                                  = sdlc_root
        self.profile_name                               = profile_name
        self.profile_path                               = f"{sdlc_root}/sdlc.profiles/{profile_name}/profile.toml" 
        self.profile                                    = UserProfile(self.profile_path)

    def setup(self, project, filter=None, operate=False, root_folder=None):
        '''
        For the given project, it clones and configures all repos for that project that are specified in 
        the user profile `self.profile_name`.

        The repos are created in a project folder under the profile's root folder for local development.

        :param str project: name of the project to set up. Must be a project that appears in 
                            self.profile["projects"]
        :param list[str] filter: optional parameter with the names of the repos to set up. If set to `None` (the
                            default value), then all repos in `self.profile` for `project` will be set up.
                            As a boundary case, if `filter` mentions a repo that is not in `self.profile`, then it is
                            ignored.
        :param bool operate: optional parameter. If True, the setup will be made for an operate installation of the project.
                            By default is is False, in which case a development setup will be made.
        :param str root_folder: optional parameter, that defaults to None. If not None, this is the root folder in the
                            local machine under which the to create a project folder called `project`, beneath which
                            repos for `project` will get cloned. If it is None, the project folder will be 
                            as specified by the suer profile `self.profile_name` 
        '''
        #Application.app().log(f"~~~~    limon      RepoSetup   ~~~~ ")
        return asyncio.run(self._supervisor(project, filter, operate, root_folder))

    async def _supervisor(self, project, filter, operate, root_folder):

        P                                               = self.profile
        REPO_LIST                                       = P.REPO_LIST(project)

        repos_to_clone                                  = REPO_LIST if filter is None else [n for n in REPO_LIST if n in filter] 
        
        Logger.log_info(f"Will set up repos {repos_to_clone} after applying filter {filter}")

        result_l                                        =  []

        to_do                                           = [self._setup_one_repo(repo_name, project, operate, root_folder)
                                                            for repo_name in repos_to_clone]

        to_do_iter                                      = asyncio.as_completed(to_do)

        for coro in to_do_iter:
            coro_result                                 = await coro
            result_l.append(coro_result)


    async def _setup_one_repo(self, repo_name, project, operate, root_folder):
        '''
        '''
        P                                               = self.profile

        BRANCHES_TO_CREATE                              = P.BRANCHES_TO_CREATE(operate)
        LOCAL_ROOT                                      = P.LOCAL_ROOT(operate, root_folder)
        REMOTE_ROOT                                     = P.REMOTE_ROOT

        # Per CCL policy, we don't want to clone the master branch, since it should never exist locally.
        # Therefore have to clone a different branch and only bring in that branch during the cloning.
        branch_to_clone                                 = BRANCHES_TO_CREATE[0]
        kwargs                                          = {"branch": branch_to_clone}

        with Profiler(f"Setting up repo '{repo_name}'"):

            remote_url                                  = f"{REMOTE_ROOT}/{repo_name}.git"
            local_url                                   = f"{LOCAL_ROOT}/{project}/{repo_name}"
            try:
                cloned_repo                             = await asyncio.to_thread(Repo.clone_from,
                                                                                  remote_url, local_url, **kwargs)
            except Exception as ex:
                raise ValueError(f"Couldn't clone '{repo_name}'"
                                    + f"\n\tremote = {remote_url}"
                                    + f"\n\rlocal = {local_url}"
                                    + f"\n\terror = {ex}"
                                    )
            Logger.log_info(f"\t... cloned repo '{repo_name}' ...")
            
            local_git                                   = GitLocalClient(cloned_repo.working_dir)

            # Now that we cloned the repo, we may need to configure the remote to include the access token.
            # This can happen during testing, for example, where the access token is for a test robot and therefore
            # GitHub access tokens are not included in this machine's windows credentials
            #
            # We will determine if there is a need to do this based on the profile we are running under. 
            # Obviously this is a security risk, since the access token will be added in clear text to the Git
            # repo configuration. 
            # So the profile should only allow this when it is a profile for resources that don't need to be protected,
            # such as a test robot acting on discardable GitHub repos that only exist for testing purposes.
            # 
            if P.OK_TO_DISPLAY_TOKEN():
                DOMAIN                              = f"https://{P.USER}:{Secrets.GIT_HUB_TOKEN()}@github.com"
                PATH                                = f"{P.GH_ORGANIZATION}/{repo_name}.git"
                await local_git.execute(command           = f"git config --local remote.origin.url {DOMAIN}/{PATH}")



            for branch in BRANCHES_TO_CREATE[1:]:
            
                # Only create branch with '-b' option if it already exists.
                if await local_git.execute(command             = f"git branch --list {branch}") == "":
                    await local_git.execute(command            = f"git checkout -b {branch}")
                else:
                    await local_git.execute(command            = f"git checkout {branch}")

                # Check if branch exists in remote. If not, push local branch. If yes, set it as the upstream.
                if await local_git.execute(command             = f"git ls-remote --heads origin {branch}") == "":
                    await local_git.execute(command            = f"git push origin -u {branch}")
                else:
                    await local_git.execute(command            = f"git branch --set-upstream-to=origin/{branch} {branch}")

            Logger.log_info(f"\t... created branches {BRANCHES_TO_CREATE[1:]} for repo '{repo_name}' ...")
            
            with Profiler(f"\tConfiguring repo '{repo_name}' ..."):
                await self.configure(cloned_repo.working_dir)

        # By away of status, return the repo_name so the caller knows which repo was created
        return repo_name


    async def configure(self, repo_path):
        '''
        Configures a local repo as per the CCL standards.

        :param str repo_path: path in the local file system for a GIT repo.

        '''
        P                                               = self.profile

        USER                                            = P.USER
        USER_EMAIL                                      = P.USER_EMAIL
        BC_PATH                                         = P.BC_PATH
        WIN_CRED_PATH                                   = P.WIN_CRED_PATH


        local_git                                       = GitLocalClient(repo_path)
        # At present, credentials manager configuration is global and done in ~/.bashrc, so comment it for now
        #
        #local_git.execute(command                       = f'git config --local credential.helper "{WIN_CRED_PATH}"')
        #local_git.execute(command                       = f'git config --local credential.https://dev.azure.com.usehttppath true')
        
        await local_git.execute(command                 = f'git config --local user.name "{USER}"')
        await local_git.execute(command                 = f'git config --local user.email "{USER_EMAIL}"')
    
        await local_git.execute(command                 = f'git config --local diff.tool bc')
        
        await local_git.execute(command                 = f'git config --local difftool.prompt false')
    
        await local_git.execute(command                 = f'git config --local difftool.bc.path "{BC_PATH}"')
        await local_git.execute(command                 = f'git config --local difftool.bc.trustExitCode true')

        # GOTCHA
        # Configuring BeyondCompare to work in WSL can be tricky. These settings are based on this post:
        #
        # https://stackoverflow.com/questions/71093803/git-with-beyond-compare-4-on-wsl2-windows-11-not-opening-the-repo-version

    
        # For the difftool.bc.cmd, we need to map the local and remote paths between WSL and Windows, and to do that
        # we need to pass a setting for which the quotes can get a little tricky. 
        #
        # Ultimately this is what we want to the argument list. The 
        # last argument needs to have 2 levels of quotes since it is a composite that internally also has composites. Hence the challenge:
        #
        #  ['git',
        #   'config',
        #   '--local',
        #   'difftool.bc.cmd',
        #   '"/mnt/c/Program Files/Beyond Compare 4/BCompare.exe" "$(wslpath -aw $LOCAL)" "$(wslpath -aw $REMOTE)"'
        #  ]
        #
        # To achieve that (a string with 2 levels of quotes inside it) we need to use 3 levels of quotes (since the outer 
        # level is needed to define the string).
        #
        # That is why we use this patther for the argument to local_git.execute, where we escape the inner 
        # single quote (\') to distinguish it from the outer single quote (')
        #
        #   f'git config --local difftool.bc.cmd \'"{BC_PATH}" "$(wslpath -aw $LOCAL)" "$(wslpath -aw $REMOTE)"\''
        #
        await local_git.execute(command                 = f'git config --local difftool.bc.cmd \'"{BC_PATH}"' 
                                                            + f' "$(wslpath -aw $LOCAL)" "$(wslpath -aw $REMOTE)"\'')
    
    
        await local_git.execute(command                 = f'git config --local merge.tool bc')
    
        await local_git.execute(command                 = f'git config --local mergetool.bc.path "{BC_PATH}"')
        await local_git.execute(command                 = f'git config --local mergetool.bc.trustExitCode true')
    
        # For mergetool.bc.cmd we have the same challenges with triple quotes as described above for the difftool.bc.cmd. 
        # In this case, this # is the argument list we need:
        #
        #  ['git',
        #   'config',
        #   '--local',
        #   'mergetool.bc.cmd',
        #   '"/mnt/c/Program Files/Beyond Compare 4/BCompare.exe" "$(wslpath -aw $LOCAL)" "$(wslpath -aw $REMOTE)" "$(wslpath -aw $BASE)" "$(wslpath -aw $MERGED)"'
        #  ]
        #
        # So we again escape the inner single quote:
        #
        #   f'git config --local mergetool.bc.cmd \'"{BC_PATH}" "$(wslpath -aw $LOCAL)" "$(wslpath -aw $REMOTE)" "$(wslpath -aw $BASE)" "$(wslpath -aw $MERGED)"\''
        #
        await local_git.execute(command                 = f'git config --local mergetool.bc.cmd \'"{BC_PATH}"'
                                                            + f' "$(wslpath -aw $LOCAL)" "$(wslpath -aw $REMOTE)"'
                                                            + f' "$(wslpath -aw $BASE)"  "$(wslpath -aw $MERGED)"\'')