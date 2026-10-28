from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ACI_backend.integrations.github.worker import run_worker
from ACI_backend.integrations.verification.errors import (
    LLMProviderError,
)
from ACI_backend.integrations.verification.execution import DockerPytestRunner
from ACI_backend.integrations.verification.llm import create_openai_evaluator


class Command(BaseCommand):
    help = "Run ACI's persistent GitHub webhook and verification worker."

    def add_arguments(self, parser):
        parser.add_argument(
            "--evaluator",
            choices=["deterministic", "openai"],
            default="deterministic",
        )
        parser.add_argument(
            "--poll-interval",
            type=float,
            default=5,
            help="Seconds to wait when no queued work is available.",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process at most one webhook and one verification run.",
        )

    def handle(self, *args, **options):
        if options["poll_interval"] <= 0:
            raise CommandError("--poll-interval must be greater than zero.")
        evaluator = None
        if options["evaluator"] == "openai":
            try:
                evaluator = create_openai_evaluator()
            except LLMProviderError as error:
                raise CommandError(str(error)) from error

        test_runner = None
        if settings.ACI_ENABLE_TEST_EXECUTION:
            if not settings.ACI_TEST_WORKSPACE:
                raise CommandError(
                    "ACI_TEST_WORKSPACE is required when test execution is enabled."
                )
            if not settings.ACI_TEST_DOCKER_IMAGE:
                raise CommandError(
                    "ACI_TEST_DOCKER_IMAGE is required for automated execution."
                )
            test_runner = DockerPytestRunner(
                workspace=settings.ACI_TEST_WORKSPACE,
                image=settings.ACI_TEST_DOCKER_IMAGE,
            )

        self.stdout.write(self.style.SUCCESS("ACI worker started."))
        run_worker(
            poll_interval=options["poll_interval"],
            once=options["once"],
            evaluator=evaluator,
            test_runner=test_runner,
        )
