from datetime import datetime
from urllib.parse import quote_plus

from .generics import AbstractAPIWrapper, Commit, PushEvent, Repo


class GitlabAPIWrapper(AbstractAPIWrapper):

    DEFAULT_HOST = "gitlab.com"
    USER_ENDPOINT = "user"
    REPOS_ENDPOINT = "projects"

    @property
    def API_URL(self):
        return "https://{}/api/v3/".format(self.host)

    @property
    def REPO_BRANCH_URL(self):
        return "https://{}/{}/tree/{}".format(self.host, self.repo, self.branch)

    @property
    def EVENTS_ENDPOINT(self):
        return "/".join(["projects", quote_plus(str(self.repo)), "events"])

    @property
    def CREATE_BRANCH_ENDPOINT(self):
        return "/".join([
            "projects", quote_plus(str(self.repo)), "repository", "branches",
        ])

    @property
    def AUTH_METHODS(self):
        return [
            ("token", self.auth_token, "Private Token"),
        ]

    def get_error(self, response):
        return response.json().get("message")

    def prepare_creds(self, request):
        request.headers["PRIVATE-TOKEN"] = self.creds

    def prepare_page(self, request, page):
        request.params["page"] = str(page)

    def prepare_create_branch(self, request, branch, ref):
        request.data = {"ref": ref, "branch_name": branch}

    def process_page_count(self, response):
        return int(response.headers.get("X-Total-Pages"))

    def filter_user(self, user):
        return user.get("username")

    def filter_repos(self, repos):

        def filter_repo(repo):
            namespace = repo.get("namespace").get("name")
            project = repo.get("path")
            return Repo(namespace, project)

        return [filter_repo(repo) for repo in repos]

    def filter_commits(self, commits):

        def filter_commit(commit):
            id = commit.get("id")
            author = commit.get("author")
            author_name = author.get("name")
            author_email = author.get("email")
            message = commit.get("message").split("\n")[0]
            return Commit(id, author_name, author_email, message)

        return [filter_commit(commit) for commit in commits]

    def filter_events(self, events):

        def filter_event(event):
            data = event.get("data")
            ref = data.get("ref")
            before = data.get("before")
            after = data.get("after")
            created_at = event.get("created_at")
            date = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
            commits = self.filter_commits(data.get("commits")[::-1])
            return PushEvent(ref, before, after, date, commits)

        events = (event for event in events if event.get("action_name") == "pushed to")
        return [filter_event(event) for event in events]

    def auth_token(self):
        print('Create a personal access token with "api" scope:')
        print("https://{}/profile/personal_access_tokens".format(self.host))
        return input("Token: ")
