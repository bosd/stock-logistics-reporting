#!/usr/bin/python3
import json
import argparse
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import textwrap
from urllib.request import urlopen


class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def run(cmd):
    print(">", bcolors.OKBLUE + " ".join(cmd) + bcolors.ENDC)
    subprocess.check_call(cmd)


def get_remote():
    remotes = (
        subprocess.check_output(["git", "remote"], universal_newlines=True)
        .strip()
        .split()
    )
    for remote in remotes:
        if remote.lower() in ("upstream", "oca"):
            return remote
    return remotes[0]


def get_pr_info(org, repo, pr):
    print("testing url")
    print(f"https://api.github.com/repos/{org}/{repo}/pulls/{pr}")
    with urlopen(f"https://api.github.com/repos/{org}/{repo}/pulls/{pr}") as r:
        return json.loads(r.read())


def get_repo_info(remote):
    url = subprocess.check_output(
        ["git", "remote", "get-url", remote], universal_newlines=True
    ).strip()
    mo = re.match(r".*github\.com[:/](?P<org>[^/]+)/(?P<repo>[^.]+)", url)
    if not mo:
        raise RuntimeError(f"Could not determine GitHub repo from {url}.")
    return mo.group("org"), mo.group("repo")


def main(pr, trg_branch):
    """
    Port a GitHub PR to another branch.

    How to use:
    - install 'gh' (https://cli.github.com/)
    - clone the repository
    - run the command from the clone directory
    """
    remote = get_remote()
    org, repo = get_repo_info(remote)
    pr_info = get_pr_info(org, repo, pr)
    pr_base_branch = pr_info["base"]["ref"]
    pr_base_sha = pr_info["base"]["sha"]
    pr_head_sha = pr_info["head"]["sha"]
    run(["git", "fetch", remote, pr_base_branch])
    run(["git", "fetch", remote, f"refs/pull/{pr}/head"])
    patches_dir = tempfile.mkdtemp()
    run(["git", "format-patch", "-o", patches_dir, f"{pr_base_sha}..{pr_head_sha}"])
    run(["git", "checkout", "-B", f"{trg_branch}-{pr}-port", f"{remote}/{trg_branch}"])
    patches = [os.path.join(patches_dir, f) for f in sorted(os.listdir(patches_dir))]
    run(["git", "am", "-3"] + patches)
    shutil.rmtree(patches_dir)
    run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            trg_branch,
            "--title",
            f"[{trg_branch}][PORT] {pr} from {pr_base_branch}",
            "--body",
            f"Port #{pr} from {pr_base_branch} to {trg_branch}.",
            "--web",
            "--repo",
            f"{org}/{repo}",
        ]
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(main.__doc__),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pr", metavar="PR")
    parser.add_argument("trg_branch", metavar="TARGET-BRANCH")
    args = parser.parse_args()
    main(args.pr, args.trg_branch)
