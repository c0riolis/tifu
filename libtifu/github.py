from datetime import datetime
from getpass import getpass
from urllib.parse import parse_qs, urlparse

from .generics import AbstractAPIWrapper, Commit, PushEvent, Repo


class GithubAPIWrapper(AbstractAPIWrapper):

    DEFAULT_HOST = "github.com"
    USER_ENDPOINT = "user"
    REPOS_ENDPOINT = "user/repos"

    @property
    def API_URL(self):
        return "https://api.{}".format(self.host)

    @property
    def REPO_BRANCH_URL(self):
        return "https://{}/{}/tree/{}".format(self.host, self.repo, self.branch)

    @property
    def EVENTS_ENDPOINT(self):
        return "/".join(["repos", str(self.repo), "events"])

    @property
    def CREATE_BRANCH_ENDPOINT(self):
        return "/".join(["repos", str(self.repo), "git", "refs"])

    @property
    def AUTH_METHODS(self):
        return [
            ("basic", self.auth_basic, "Basic (login + password)"),
            ("oauth", self.auth_oauth, "OAuth2 (mandatory for 2FA)"),
        ]

    def get_error(self, response):
        return response.json().get("message")

    def prepare_creds(self, request):
        request.auth = self.creds

    def prepare_page(self, request, page):
        request.params["page"] = str(page)

    def prepare_create_branch(self, request, branch, ref):
        request.json = {"sha": ref, "ref": "refs/heads/{}".format(branch)}

    def process_page_count(self, response):
        last = response.links.get("last")
        if not last:
            return 1
        query_string = urlparse(last.get("url")).query
        return int(parse_qs(query_string).get("page")[-1])

    def filter_user(self, user):
        return user.get("login")

    def filter_repos(self, repos):

        def filter_repo(repo):
            namespace = repo.get("owner").get("login")
            project = repo.get("name")
            return Repo(namespace, project)

        return [filter_repo(repo) for repo in repos]

    def filter_commits(self, commits):

        def filter_commit(commit):
            id = commit.get("sha")
            author = commit.get("author")
            author_name = author.get("name")
            author_email = author.get("email")
            message = commit.get("message").split("\n")[0]
            return Commit(id, author_name, author_email, message)

        return [filter_commit(commit) for commit in commits]

    def filter_events(self, events):

        def filter_event(event):
            payload = event.get("payload")
            ref = payload.get("ref")
            before = payload.get("before")
            after = payload.get("head")
            created_at = event.get("created_at")
            date = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
            commits = self.filter_commits(payload.get("commits")[::-1])
            return PushEvent(ref, before, after, date, commits)

        events = (event for event in events if event.get("type") == "PushEvent")
        return [filter_event(event) for event in events]

    def auth_basic(self):
        login = input("Login: ")
        password = getpass("Password: ")
        return (login, password)

    def auth_oauth(self):
        print('Create a personal access token with "repo" scope:')
        print("https://{}/settings/tokens".format(self.host))
        token = input("Token: ")
        return (token, "x-oauth-basic")
