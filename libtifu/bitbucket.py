from datetime import datetime
from getpass import getpass
from json import JSONDecodeError
from urllib.parse import urljoin

import requests

from .generics import AbstractAPIWrapper, Commit, PushEvent, Repo


class BitbucketAPIWrapper(AbstractAPIWrapper):

    DEFAULT_HOST = "bitbucket.org"
    USER_ENDPOINT = "user"
    REPOS_ENDPOINT = "user/repositories"
    EVENTS_HEADER = "Select the most recent push event containing your " \
                    "erased commits:"

    @property
    def API_URL(self):
        return "https://api.{}/1.0/".format(self.host)

    @property
    def REPO_BRANCH_URL(self):
        return "https://{}/{}/branch/{}".format(self.host, self.repo, self.branch)

    @property
    def EVENTS_ENDPOINT(self):
        return "/".join(["repositories", str(self.repo), "events"])

    @property
    def CREATE_BRANCH_ENDPOINT(self):
        return "/".join(["branch", "create"])

    @property
    def AUTH_METHODS(self):
        return [
            ("basic", self.auth_basic, "Basic (login + password)"),
        ]

    def get_error(self, response):
        # Bitbucket returns full HTML error pages
        try:
            return response.json().get("error").get("message")
        except JSONDecodeError:
            return response.reason

    def prepare_creds(self, request):
        request.auth = self.creds

    def prepare_page(self, request, page):
        # Bitbucket API does not use pagination for repository list
        # and event endpoint is capped at 31 events. Set limit at 50
        # so we always have one page.
        request.params["limit"] = 50

    def prepare_create_branch(self, request, branch, ref):
        request.data = {
            "repository": str(self.repo),
            "from_branch": ref,
            "branch_name": branch,
        }

    def process_page_count(self, response):
        # We will never have more than one page (see prepare_page).
        return 1

    def filter_user(self, user):
        return user.get("user").get("username")

    def filter_repos(self, repos):

        def filter_repo(repo):
            namespace = repo.get("owner")
            project = repo.get("slug")
            return Repo(namespace, project)

        return [filter_repo(repo) for repo in repos]

    def filter_commits(self, commits):

        def filter_commit(commit):
            id = commit.get("hash")
            author_name = ""
            author_email = ""
            message = commit.get("description").split("\n")[0]
            return Commit(id, author_name, author_email, message)

        return [filter_commit(commit) for commit in commits]

    def filter_events(self, events):

        def filter_event(event):
            description = event.get("description")
            ref = description.get("ref")
            before = None
            created_on = event.get("created_on")
            date = datetime.strptime(created_on, "%Y-%m-%dT%H:%M:%S")
            commits = self.filter_commits(description.get("commits"))
            after = commits[0].id
            return PushEvent(ref, before, after, date, commits)

        events = (event for event in events if event.get("event") == "pushed")
        return [filter_event(event) for event in events]

    def get_events(self):
        request = self.request(self.EVENTS_ENDPOINT, "GET")
        events = self.send_request(request, requests.codes.ok).json()
        return self.filter_events(events.get("events"))

    def create_branch(self, branch, ref):
        # Bitbucket API does not provide a way to create branches.
        # Directly use the website instead.
        url = urljoin("https://{}/".format(self.host), self.CREATE_BRANCH_ENDPOINT)
        request = requests.Request("POST", url)
        self.prepare_create_branch(request, branch, ref)
        self.send_request(request, requests.codes.ok)

    def attach_old_ref(self):
        branch = "tifu-{}".format(self.event.after)
        self.create_branch(branch, self.event.after)
        return branch

    def auth_basic(self):
        login = input("Login: ")
        password = getpass("Password: ")
        return (login, password)
