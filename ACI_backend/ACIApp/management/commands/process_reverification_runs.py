from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ACI_backend.integrations.verification.llm import create_openai_evaluator
from ACI_backend.integrations.verification.service import (
    collect_repository_code_evidence,
    process_next_reverification_run,
    recover_stuck_reverification_runs,
)
from ACI_backend.integrations.verification.execution import (
    DockerPytestRunner,
)


class Command(BaseCommand):
    help = "Process queued ACI re-verification runs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--evaluator",
            choices=["deterministic", "openai"],
            default="deterministic",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum runs to process; 0 means no limit.",
        )

    def handle(self, *args, **options):
        recover_stuck_reverification_runs()
        evaluator = None
        if options["evaluator"] == "openai":
            evaluator = create_openai_evaluator()
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
        processed = 0

        while (
            options["limit"] == 0 or processed < options["limit"]
        ) and process_next_reverification_run(
            evaluator=evaluator,
            test_runner=test_runner,
            source_evidence_collector=collect_repository_code_evidence,
        ) is not None:
            processed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {processed} re-verification run(s)."
            )
        )
