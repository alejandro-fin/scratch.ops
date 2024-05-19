import asyncio

import git                                                          as _git
from pathlib                                                        import Path

from conway.application.application                                 import Application
from conway.util.command_parser                                     import CommandParser

class GitLocalClient():

    '''
    Helper class used to invoke GIT commands as strings. It essentially is a wrapper around GitPython to avoid having
    awareness of GitPython across Conway modules.

    :param str repo_path: Location in the file system for the Git repository to be acted on by this :class:`GitLocalClient` instance.

    '''
    def __init__(self, repo_path):

        # GOTCHA: 
        #   If the repo_path does not exist (as it has happened due to typo by the user in setting inputs)
        #   then unfortunately the GitPython's cmd.Git constructor will not fail and will just use a previous repo from
        #   some prior instance of cmd.Git (e.g, looks like it does some static caching). That is very bad since then 
        #   subsequent processing will be manipulating *the wrong repo*.
        #
        #   So force an exception in repo_path is not set correctly.
        #
        if not Path(repo_path).exists():
            raise ValueError("Repo folder does not exist: '" + str(repo_path) + "'")
        
        self.executor                                       = _git.cmd.Git(repo_path)

    async def execute(self, command):
        '''
        :param str command: a GIT command to execute. Example: "git status"
        :return: the result of attempting to invoke the GIT ``command``
        :rtype: str
        '''
        #Application.app().log(f"~~~~    limon     async  GitLocalClient   ~~~~ ")

        # GOTCHA: On Linux, GitPython requires commands with arguments to be passed as a list, not
        #       as a string. Thus, a command like "git status" should be passed in Linux as
        #       ["git", "status"]
        #
        # That is why we split the command parameter
        #
        args_list                                           = CommandParser().get_argument_list(command)
        
        try:
            response                                        = await asyncio.to_thread(self.executor.execute,
                                                                                        args_list)

            return response
        except Exception as ex:
            raise ValueError("Could not run GIT command '" + str(command) + "'." 
                             + "\n\t==> Often this happens due to GIT authentication issues. "
                             + "\n\t==>If so, it's recommended to generate SSH keys as explained in "
                             + "\n\t\thttps://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent?platform=linux"
                             + "\n\nError message is:\n"
                             + str(ex))