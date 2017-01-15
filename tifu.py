#! /usr/bin/env python3

from argparse import ArgumentParser
from re import match

from libtifu.bitbucket import BitbucketAPIWrapper
from libtifu.github import GithubAPIWrapper
from libtifu.gitlab import GitlabAPIWrapper


SERVICES = {
        "bitbucket": BitbucketAPIWrapper,
        "github": GithubAPIWrapper,
        "gitlab": GitlabAPIWrapper,
}


class ArgumentException(Exception):
    pass


def main():
    APIS = ["github", "gitlab", "bitbucket"]

    parser = ArgumentParser()
    parser.add_argument("remote", nargs="?", help="git remote")
    parser.add_argument(
            "-a", "--api", choices=APIS, metavar="",
            help="API to use ({})".format(", ".join(APIS)),
    )
    parser.add_argument("--host", help="server hostname")
    parser.add_argument(
            "-r", "--repo", metavar="REPO",
            help="repository name (namespace/project)",
    )
    args = parser.parse_args()

    if not args.remote and not args.api and not args.host:
        raise ArgumentException("Please specify at least an API or a remote.")

    if args.remote:
        if args.remote.endswith(".git"):
            args.remote = args.remote[:-4]
        rem = match(r"^(https://([^/]+)/(.+)|git@([^/]+):(.*))$", args.remote)
        if rem:
            args.host = rem.group(2) or rem.group(4)
            args.repo = rem.group(3) or rem.group(5)
        else:
            raise ArgumentException("Bad remote format.")

    if args.host in ["github.com", "gitlab.com", "bitbucket.org"]:
        args.api = args.host[:-4]

    if not args.api:
        raise ArgumentException("Unable to guess API, please specify it.")

    wrapper = SERVICES[args.api](args.repo, args.host)
    wrapper.execute()


if __name__ == "__main__":
    try:
        main()
    except ArgumentException as e:
        print(e)
    except (KeyboardInterrupt, EOFError):
        print("\nInterrupted")
