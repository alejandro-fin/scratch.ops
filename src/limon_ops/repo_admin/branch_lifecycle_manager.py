import os                                                           as _os

from conway.application.application                                 import Application

from limon_ops.repo_admin.repo_administration                      import RepoAdministration
from conway_ops.repo_admin.repo_inspector_factory                   import RepoInspectorFactory
from conway_ops.util.git_branches                                   import GitBranches
from conway_ops.util.git_local_client                                     import GitLocalClient

class BranchLifecycleManager(RepoAdministration):

    '''
    Extends parent class to support a higher-level library for the common GIT branch management workflows
    appertaining to a Conway-based application's development processes. These workflows are as follows:

    * There are 3 special branches that developers don't typically manipulate directly:

        * Master
        * Integration
        * Operate

    * In addition, for each unit of work there is a feature branch

    * Code changes flows as follows:

        * Master can only change via pull requests from integration or from operate, and only remotely.

        * Operate is never used for development, only to run production workloads
        
            * It is ocassionally used for hot fixes
            * Only branch it connects to is master, and only in the remote (via pull requests in either direction)

        * Feature branches is where development happens

            * They can only deliver content to integration, and only locally (via a git merge encapsulated
              by a method of this class)
            * Tests must pass and all feature work completed when the feature branch delivers onto integration.
              There are no deliveries to integration for "partially completed" feature work.
            * There is no connection between a feature branch and master, operate, or any other feature branch,
              neither locally or in the remote.
            * Developers use the CLI to git push to the remote feature branch, as a cloud backup only. The remote
              feature branch is not connected to anything.

        * Integration is final validation before merging to master

            * Integration is where the changes from multiple feature branches are tested together.

            * In addition to passing all tests, in integration an additional test is made to run the production
              scripts end-to-end.

    For example, the flow for a feature branch to submit changes is:

        feature branch (local) => integration (local) => integration (remote) => master (remote)

    And the flow to update operate is

        master(remote) => operate (remote) => operate (local)

    These flows can also flow in the inverse direction.

    :param str local_root: Folder or URL of the parent folder for all local GIT repos.

    :param str remote_root: Folder or URL of the parent folder for the remote GIT repos

    :param RepoBundle repo_bundle: Object encapsulating the names of the GIT repos for which joint GIT operations 
        are to be done by this :class:`RepoAdministration` instance.

    :param str remote_gh_user: GitHub username with rights to the remote repository. If the remote is not in
        GitHub, it may be set to None

    :param str gh_secrets_path: path in the local file system for a file that contains a GitHub token to access the remote.
        The token must correspond to the user given by the `remote_gh_user` parameter. If the remote is not in GitHub
        then it may be set to None

    '''
    def __init__(self, local_root, remote_root, repo_bundle, remote_gh_user, remote_gh_organization, gh_secrets_path):

        super().__init__(local_root, remote_root, repo_bundle, remote_gh_user, remote_gh_organization, gh_secrets_path)

    def pull_request_integration_to_master(self):
        '''
        Does a pull request to update the remote master from the remote integration, and vice versa.
        '''
        GB                                              = GitBranches
        app_name                                        = Application.app().app_name
        master                                          = GB.MASTER_BRANCH.value
        integration                                     = GB.INTEGRATION_BRANCH.value
        for repo_name in self.repo_names():
            self.log_info(f"\n----------- {repo_name} (remote) -----------")

            inspector                                   = RepoInspectorFactory.findInspector(self.remote_root,
                                                                                             repo_name)

            downstream_pr                               = inspector.pull_request(
                                                            from_branch          = master, 
                                                            to_branch            = integration,
                                                            title                = f"Merge {master} -> {integration} (remote)",
                                                            body                 = f"Automated PR creation by {app_name}")
            
            upstream_pr                                 = inspector.pull_request(
                                                            from_branch          = integration, 
                                                            to_branch            = master,
                                                            title                = f"Merge {integration} -> {master} (remote)",
                                                            body                 = f"Automated PR creation by {app_name}")

    def publish_release(self):
        '''
        This is used when the remote master branch contains a new release, arising from the development
        workflows: feature branches were merged into integration, and the remote integration branch was
        merged into the remote master.

        In that situation, to "publish" the release means to update the operate branch (remote and local)
        with the contents of the release.

        Theterfore, this method does a pull request to update the remote operate branch from the remote master branch,
        and the updates the local operate branch from the remote.

        End effect is that we "published" a release from the remote master branch to the local operate
        branch.
        '''
        GB                                              = GitBranches
        app_name                                        = Application.app().app_name
        master                                          = GB.MASTER_BRANCH.value
        operate                                         = GB.OPERATE_BRANCH.value            
        for repo_name in self.repo_names():
            self.log_info(f"\n----------- {repo_name} (remote) -----------")

            remote_inspector                            = RepoInspectorFactory.findInspector(self.remote_root,
                                                                                             repo_name)
            remote_inspector.pull_request(from_branch   = master, 
                                          to_branch     = operate,
                                          title         = f"Merge {master} -> {operate} (remote)",
                                          body          = f"Automated PR creation by {app_name}")
            
            self.log_info(f"\n----------- {repo_name} (local) -----------")

            local_inspector                            = RepoInspectorFactory.findInspector(self.local_root,
                                                                                             repo_name)


            local_inspector.update_local(operate)

    def publish_hot_fix(self):
        '''
        A "hot fix" is a change that is implemented in the local operate branch. To publish the "hot fix"
        means to make the change available to the official release line (the master branch) as well as to
        the development process (that works off the integration branch).

        This method expects that the developer already pushed the local work to the remote operate branch.
    
        Therefore, this method:

        1. Does a pull request from the (remote) operate branch to the (remote) master branch
        2. Does a pull request from the (remote) master branch to the (remote) integration branch
        3. Does a pull to the local integration branch.
        '''
        GB                                              = GitBranches
        app_name                                        = Application.app().app_name
        master                                          = GB.MASTER_BRANCH.value
        integration                                     = GB.INTEGRATION_BRANCH.value
        operate                                         = GB.OPERATE_BRANCH.value            

        for repo_name in self.repo_names():

            remote_inspector                            = RepoInspectorFactory.findInspector(self.remote_root, repo_name)
            local_inspector                             = RepoInspectorFactory.findInspector(self.local_root, repo_name)

            self.log_info(f"\n----------- {repo_name} (remote) -----------")

            # Update operate => master (remote)
            remote_inspector.pull_request(from_branch   = operate, 
                                          to_branch     = master,
                                          title         = f"Merge {operate} -> {master} (remote)",
                                          body          = f"Automated PR creation by {app_name}")

            # Update master => integration (remote)
            remote_inspector.pull_request(from_branch   = master, 
                                          to_branch     = integration,
                                          title         = f"Merge {master} -> {integration} (remote)",
                                          body          = f"Automated PR creation by {app_name}")

            self.log_info(f"\n----------- {repo_name} (local) -----------")
            # Now update local integration from the remote
            local_inspector.update_local(integration)

    def complete_feature(self, feature_branch):
        '''
        Merges a feature branch into the integration branch locally, and pushes the integration branch.

        After the merge, it will leave the local repo in the same branch that was checked out prior to this
        method getting called.

        Raises an exception if there is uncommitted work in the feature branch.
        '''
        GB                                              = GitBranches
        integration                                     = GB.INTEGRATION_BRANCH.value

        
        for repo_name in self.repo_names():
            self.log_info(f"\n----------- {repo_name} (local) -----------")
            # First check that there is nothing checked out

            working_dir                                 = self.local_root + "/" + repo_name
            _os.chdir(working_dir)
            self.log_info(f"local = '{working_dir}'")
            executor                                    = GitLocalClient(working_dir)

            if feature_branch == integration:
                raise ValueError(f"A self-referencing merge '{feature_branch}' -> '{integration}' is not allowed. Are "
                                 + f"you sure you provided the correct feature branch to merge into '{integration}'?")

            original_branch                             = executor.execute(command = "git rev-parse --abbrev-ref HEAD")

            # First check if there is anything to commit. We check because if there is nothing to commit
            # and we try to commit, we will get error messages
            status                                      = self._STATUS(executor, original_branch)
        
            CLEAN_TREE_MSG                              = "nothing to commit, working tree clean"
            if not CLEAN_TREE_MSG in status:
                raise ValueError(f"Can't merge '{feature_branch}' -> '{integration}' because there is unchecked work in "
                                  + f"'{original_branch}':\n\t{status}")
            
            # Before merging the feature branch, update the local integration branch with other people's changes
            # by pulling integration from the remote
            #
            self._TO(executor, integration)

            self._PULL(executor, integration)

            # Now that the local integration branch has other people's changes, bring them into the feature
            # branch. This step may result in a merge
            #
            self._TO(executor, feature_branch)

            self._MERGE(executor, integration, feature_branch)

            # If we get this far, then the feature branch now other people's change in it. It is now safe
            # for the feature branch to be merged into integration, locally andin the remote
            #
            self._TO(executor, integration)

            self._MERGE(executor, feature_branch, integration)

            self._PUSH(executor, integration)

            # Leave the repo in the same branch in which we found it
            #
            if original_branch != integration:
                self._TO(executor, original_branch)
 
    def _STATUS(self, executor, branch):
        '''
        Helper method to get status of a branch. It requires that `branch` is the current branch.
        '''
        status                                      = executor.execute(command = 'git status')
        self.log_info(f"@ '{branch}' (local):\n\n{status}") 
        return status

    def _TO(self, executor, branch):
        '''
        Helper method to switch to the given branch
        '''
        status                                      = executor.execute("git checkout " + branch)
        self.log_info(f"@ '{branch}' (local):\n\n{status}")
        return status

    def _MERGE(self, executor, from_branch, to_branch):
        '''
        Helper method to do a merge between local branches. It requires that `from_branch` is the current branch.
        '''
        status                                      = executor.execute("git merge " + str(from_branch))
        self.log_info(f"'{from_branch}' (local) - {to_branch}' (local):\n\n{status}")
        return status

    def _PULL(self, executor, branch):
        '''
        Helper method to pull remote to local. It requires that `branch` be the current branch.
        '''
        status                                     = executor.execute(command = 'git pull')
        self.log_info(f"{branch} (remote) ->'{branch} (local)':\n\n{status}") 
        return status

    def _PUSH(self, executor, branch):
        '''
        Helper method to push local to remote. It requires that `branch` be the current branch.
        '''
        status                                      = executor.execute(command = 'git push')
        self.log_info(f"{branch}' (local) -> {branch}' (remote):\n\n{status}")
        return status 


    def commit_feature(self, feature_branch, commit_msg):
        '''
        Commits all (local) work in a feature branch using the common commit comment ``commit_msg`` and pushes
        everything to the remote.
        
        Raises an exception if the current branch is not the same as ``feature_branch``

        :param str feature_branch: name of branch to commit
        :param str commit_msg: comment to apply in the commits

        '''
        for repo_name in self.repo_names():
            current_branch                              = self.current_local_branch(repo_name)
            if feature_branch != current_branch:
                raise ValueError("Can't commit work because repo '" + repo_name + "' has the wrong branch checked out: '"
                                 + current_branch + "' (should have been '" + feature_branch + "')") 
        for repo_name in self.repo_names():
            self.log_info(f"\n----------- {repo_name} (local) -----------")

            working_dir                                 = self.local_root + "/" + repo_name
            _os.chdir(working_dir)
            self.log_info("local = '" + working_dir + "'")
            executor                                    = GitLocalClient(working_dir)

            # First check if there is anything to commit. We check because if there is nothing to commit
            # and we try to commit, we will get error messages
            status                                      = self._STATUS(executor, feature_branch) 
        
            CLEAN_TREE_MSG                              = "nothing to commit, working tree clean"
            if not CLEAN_TREE_MSG in status:            
                status1                                 = executor.execute(command = 'git add .')
                self.log_info(f"'{feature_branch}' (working tree) -> '{feature_branch}' (staging area):\n{status1}") 
                # GOTCHA
                #   Git commit will fail unless the commit message is surrounded by *double* quotes (will fail if using single
                #   quote)
                #       UPSHOT: nest double quotes inside single quotes: the command is a string defined by single quotes
                status2                                 = executor.execute(command = 'git commit -m "' + str(commit_msg) + '"')
                self.log_info(f"'{feature_branch}' (staging area) -> '{feature_branch}' (local):\n{status2}") 
            
            # When the remote is in GitHub, for the git push to work, we will need to use our specific owner and 
            # token for the remote. So set them up if needed:
            #
            if not self.github_token is None and not self.remote_gh_user is None:
                USER                                    = self.remote_gh_user
                GH_ORGANIZATION                         = self.remote_gh_organization
                PWD                                     = self.github_token
                CMD                                     = f"git remote set-url origin https://{USER}:{PWD}@github.com/{GH_ORGANIZATION}/{repo_name}.git"
                executor.execute(command = CMD)

            try:
                status3                                 = executor.execute(command = 'git push')
            except Exception as ex:
                self.log_info(f"Error during 'git push' - sometimes this is due to missing credentials."
                              + f" If 'git config --get credential.helper' returns 'manager', then GIT is using the Windows "
                              + f"Credentials Manager, and it is probably not correctly configured for the remote's URL. "
                              + f"If instead GIT is using a GIT-specific credential store, look at "
                              + f"https://git-scm.com/docs/gitcredentials. Also check out "
                              + f"https://github.com/git-ecosystem/git-credential-manager/blob/main/docs/multiple-users.md")
                raise ex

            self.log_info(f"'{feature_branch}' (local) -> '{feature_branch}' (remote):\n{status3}") 

    def commit_hot_fix(self, commit_msg):
        '''
        Commits all (local) work in operate branch using the common commit comment ``commit_msg`` and pushes
        everything to the remote.
        
        Raises an exception if the current branch is not the operate branch.

        :param str feature_branch: name of branch to commit
        :param str commit_msg: comment to apply in the commits

        '''
        GB                                              = GitBranches
        return self.commit_feature(GB.OPERATE_BRANCH.value, commit_msg)

    def work_on_feature(self, feature_branch):
        '''
        Switches all repos to the ``feature_branch``. If it does not exist, it is created in both local
        and remote.

        NB: The remote branch is a terminal endpoint, since submission of work is via the integration branch.
        It is created, though, to provide backup functionality: any push in the feature branch 
        '''
        for repo_name in self.repo_names():

            repo_path                                   = self.local_root + "/" + repo_name

            executor                                    = GitLocalClient(repo_path)
            existing_branches                           = self.branches(repo_name)

            self.log_info(f"\n----------- {repo_name} (local) -----------")

            if feature_branch in existing_branches:
                # In this case, we just switch to the branch
                status                                  = executor.execute("git checkout " + str(feature_branch))
                self.log_info(f"@ '{feature_branch}' (local):\n\n{status}")
            else:
                # In this case create the branch, and set tracking in the remote
               
                status1                                 = executor.execute(command = 'git checkout -b ' + str(feature_branch))
                self.log_info(f"Created'{feature_branch}' (local):\n\n{status1}") 
                status2                                 = executor.execute(command = 'git push -u origin ' + str(feature_branch))
                self.log_info(f"Tracking '{feature_branch} (local) <-> (remote)':\n\n{status2}") 

    def remove_feature_branch(self, feature_branch):
        '''
        Removes the local and remote branch called ``feature_branch`` across all repos, provided that the local
        branch has been already merged into the integration branch. If some repo hasn't been merged into the integration branch
        then it raises an exception and does not remove the branch in any repo.
        '''
        GB                                              = GitBranches
        integration                                     = GB.INTEGRATION_BRANCH.value

        # First check that everything was merged already to the integration branch
        unmerged_repos                                  = []
        
        for repo_name in self.repo_names():
            if not self.is_branch_merged_to_destination(repo_name, 
                                                        branch_name         = feature_branch, 
                                                        destination_branch  = integration):
                unmerged_repos.append(repo_name)

        if len(unmerged_repos) > 0:
            raise ValueError("Can't remove branch '" + str(feature_branch) + "' because it has not yet been merged "
                             + " with the '" + integration + "' branch in these repo(s): "
                             + ", ".join(unmerged_repos))
        
        # If we get this far, then all work has been merged, so we can safely remove the branch
        for repo_name in self.repo_names():
            executor                                    = GitLocalClient(self.local_root + "/" + repo_name)

            self.log_info(f"\n----------- {repo_name} (local) -----------")

            status1                                     = executor.execute(
                                                                    command = 'git branch -d  ' + str(feature_branch))
            self.log_info("Deleted local '" + str(feature_branch) + "':\n" + str(status1)) 
            status2                                     = executor.execute(
                                                                    command = 'git push origin --delete  ' + str(feature_branch))
            self.log_info("Deleted remote '" + str(feature_branch) + "':\n" + str(status2)) 

    def refresh_from_integration(self, feature_branch):
        '''
        Cascade changes from the remote integration branch to the local feature branch, and switches to the local
        feature branch.
        '''
        GB                                              = GitBranches
        app_name                                        = Application.app().app_name
        integration                                     = GB.INTEGRATION_BRANCH.value
        for repo_name in self.repo_names():
            self.log_info(f"\n----------- {repo_name} (local) -----------")

            local_inspector                             = RepoInspectorFactory.findInspector(self.local_root, repo_name)

            # First, refresh the local integration branch from the remote integration branch
            local_inspector.update_local(integration)

            # Now merge integration into feature branch
            local_inspector.pull_request(from_branch    = integration, 
                                         to_branch      = feature_branch,
                                         title          = f"Merge {integration} -> {feature_branch} (local)",
                                         body           = f"Automated PR creation by {app_name}")

    def refresh_from_remote(self, feature_branch):
        '''
        Updates local feature branch from the remote feature branch.
        '''
        for repo_name in self.repo_names():
            self.log_info(f"\n----------- {repo_name} (local) -----------")

            local_inspector                             = RepoInspectorFactory.findInspector(self.local_root, repo_name)

            # First, refresh the local integration branch from the remote integration branch
            local_inspector.update_local(feature_branch)

