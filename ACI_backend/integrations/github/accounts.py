from django.db.models import Q

from ACI_backend.ACIApp.models import GitHubAccount, PullRequest, Repository


def link_github_account_repositories(account):
    repositories = Repository.objects.filter(
        Q(owner__iexact=account.github_login)
        | Q(pull_requests__author__iexact=account.github_login)
    ).distinct()
    for repository in repositories:
        repository.members.add(account.user)


def link_repository_github_members(repository):
    user_ids = account_user_ids_for_repository(repository)
    if user_ids:
        repository.members.add(*user_ids)


def account_user_ids_for_repository(repository):
    pull_request_authors = PullRequest.objects.filter(
        repository=repository,
    ).values("author")
    return GitHubAccount.objects.filter(
        Q(github_login__iexact=repository.owner)
        | Q(github_login__in=pull_request_authors)
    ).values_list("user_id", flat=True)
