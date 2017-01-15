from abc import ABC, abstractmethod, abstractproperty
from math import log10
from urllib.parse import urljoin
from textwrap import indent

import requests


class Repo():

    def __init__(self, namespace, project):
        self.namespace = namespace
        self.project = project

    def __str__(self):
        return "{}/{}".format(self.namespace, self.project)


class Commit():

    def __init__(self, id, author_name, author_email, message):
        self.id = id
        self.author_name = author_name
        self.author_email = author_email
        self.message = message

    def __str__(self):
        s = "{} - {}".format(self.id[:8], self.message)
        if self.author_name and self.author_email:
            s += " [{} <{}>]".format(self.author_name, self.author_email)
        return s


class PushEvent():

    def __init__(self, ref, before, after, date, commits):
        self.ref = ref
        self.before = before
        self.after = after
        self.date = date
        self.commits = commits

    def __str__(self):
        return "[{}] {} -> {} @ {}".format(
            self.ref, self.before[:8], self.after[:8], self.date,
        )


class APIException(Exception):
    pass


class AbstractAPIWrapper(ABC):

    @abstractproperty
    def DEFAULT_HOST(self):
        pass

    @abstractproperty
    def API_URL(self):
        pass

    @abstractproperty
    def REPO_BRANCH_URL(self):
        pass

    @abstractproperty
    def USER_ENDPOINT(self):
        pass

    @abstractproperty
    def REPOS_ENDPOINT(self):
        pass

    @abstractproperty
    def EVENTS_ENDPOINT(self):
        pass

    @abstractproperty
    def CREATE_BRANCH_ENDPOINT(self):
        pass

    @abstractproperty
    def AUTH_METHODS(self):
        pass

    @abstractmethod
    def get_error(self, response):
        pass

    @abstractmethod
    def prepare_creds(self, request):
        pass

    @abstractmethod
    def prepare_page(self, request, page):
        pass

    @abstractmethod
    def prepare_create_branch(self, request, branch, ref):
        pass

    @abstractmethod
    def process_page_count(self, response):
        pass

    @abstractmethod
    def filter_user(self, user):
        pass

    @abstractmethod
    def filter_repos(self, repos):
        pass

    @abstractmethod
    def filter_commits(self, commit):
        pass

    @abstractmethod
    def filter_events(self, events):
        pass

    AUTHS_HEADER = "Select authentication method:"
    AUTHS_EMPTY = "No authentication method available."
    REPOS_HEADER = "Select repository:"
    REPOS_EMPTY = "No repositories."
    EVENTS_HEADER = "Select the push event that erased your commits:"
    EVENTS_EMPTY = "No push events."

    def __init__(self, repo, host):
        self.repo = repo
        self.host = host or self.DEFAULT_HOST
        self.auth_method = None
        self.auth_fcn = None
        self.creds = None
        self.event = None
        self.branch = None

    def request(self, endpoint, method=None):
        return requests.Request(method, url=urljoin(self.API_URL, endpoint))

    def send_request(self, request, expected_code):
        session = requests.Session()
        self.prepare_creds(request)
        response = session.send(session.prepare_request(request))
        if response.status_code != expected_code:
            raise APIException(self.get_error(response))
        return response

    def get_page_count(self, request):
        request.method = "HEAD"
        response = self.send_request(request, requests.codes.ok)
        return self.process_page_count(response)

    def get_page(self, request, page):
        request.method = "GET"
        self.prepare_page(request, page)
        return self.send_request(request, requests.codes.ok).json()

    def get_all_pages(self, request):
        page_count = self.get_page_count(request)
        elements = []
        for i in range(1, page_count + 1):
            elements += self.get_page(request, i)
        return elements

    def get_user(self):
        request = self.request(self.USER_ENDPOINT, "GET")
        user = self.send_request(request, requests.codes.ok).json()
        return self.filter_user(user)

    def get_repos(self):
        request = self.request(self.REPOS_ENDPOINT)
        repos = self.get_all_pages(request)
        return sorted(self.filter_repos(repos), key=lambda x: str(x).lower())

    def get_events(self):
        request = self.request(self.EVENTS_ENDPOINT)
        events = self.get_all_pages(request)
        return self.filter_events(events)

    def create_branch(self, branch, ref):
        request = self.request(self.CREATE_BRANCH_ENDPOINT, "POST")
        self.prepare_create_branch(request, branch, ref)
        self.send_request(request, requests.codes.created)

    def attach_old_ref(self):
        branch = "tifu-{}".format(self.event.before)
        self.create_branch(branch, self.event.before)
        return branch

    def print_auth_method(self, i, size, method):
        _, _, method_desc = method
        print("[{0:>{1}}] {2}".format(i, size, method_desc))

    def print_repo(self, i, size, repo):
        print("[{0:>{1}}] {2}".format(i, size, repo))

    def print_event(self, i, size, event):
        header = "[{0:>{1}}] Date: {2}".format(i, size, event.date)
        details = "Ref: {}\n".format(event.ref) if event.ref else ""
        details += "Old head: {}\n".format(event.before) if event.before else ""
        details += "New head: {}\n* Commits:".format(event.after)
        commits = ("* {}".format(commit) for commit in event.commits)
        print(header)
        print(indent(details, (size + 3) * " "))
        print(indent("\n".join(commits), (size + 7) * " "))
        print()

    def print_success(self):
        print("Success! Your restored commits are on branch {}".format(self.branch))
        print(self.REPO_BRANCH_URL)

    def print_failure(self, error):
        print("Oops. Something went wrong :(")
        print("Error: {}".format(error))

    def print_and_select(self, header, empty, print_fcn, elements, fast=False):
        if not elements:
            print(empty)
            return None
        if fast and len(elements) == 1:
            return elements[0]
        print(header)
        size = int(log10(len(elements))) + 1
        for i, element in enumerate(elements, start=1):
            print_fcn(i, size, element)
        choice = -1
        while not 0 < choice <= len(elements):
            try:
                choice = int(input("Choice: "))
            except ValueError:
                continue
        return elements[choice - 1]

    def select_auth_method(self):
        return self.print_and_select(
            self.AUTHS_HEADER, self.AUTHS_EMPTY, self.print_auth_method,
            self.AUTH_METHODS, fast=True,
        )

    def select_repo(self):
        repos = self.get_repos()
        return self.print_and_select(
            self.REPOS_HEADER, self.REPOS_EMPTY, self.print_repo, repos,
        )

    def select_event(self):
        events = self.get_events()
        return self.print_and_select(
            self.EVENTS_HEADER, self.EVENTS_EMPTY, self.print_event, events,
        )

    def get_creds(self):
        self.auth_method, auth_fcn, _ = self.select_auth_method()
        return auth_fcn()

    def execute(self):
        try:
            self.creds = self.get_creds()
            print()
            user = self.get_user()
            print("Authenticated as user {}.\n".format(user))
            if not self.repo:
                self.repo = self.select_repo()
                print()
            if not self.repo:
                return
            self.event = self.select_event()
            print()
            if not self.event:
                return
            self.branch = self.attach_old_ref()
            self.print_success()
        except APIException as e:
            self.print_failure(e)
