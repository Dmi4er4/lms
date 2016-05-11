# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from itertools import chain

import tablib

from django.core.management import BaseCommand, CommandError

from learning.admission.import_export import OnlineTestRecordResource
from learning.admission.models import Applicant


class Command(BaseCommand):
    help = (
        """Import results for online test. Run in dry mode by default.

        Try to find already existed online test by `lookup` field
        and campaign_id and update record if score is less than previous.
        Note: This command creates online test result record only for
            yandex login registered in our database.
            Run `online_test_init` first to create empty records for
            all applicants, even with buggy yandex login.
        Note: Don't forget manually remove applicant duplicates first
            to avoid errors on `attach_applicant` action.

        Example:
        ./manage.py online_test_import_results ~/online-test-results.csv --campaign_id=1 --lookup=stepic_id
        """
    )
    # Other fields go to dynamically created `details` field
    allowed_fields = ['created', 'yandex_id', 'stepic_id', 'score', 'yandex_contest_id', 'user_name']
    lookup_fields = ["yandex_id", "stepic_id"]

    def add_arguments(self, parser):
        parser.add_argument('csv', metavar='CSV',
                   help='path to csv with data')

        parser.add_argument('--campaign_id', type=int,
            dest='campaign_id',
            help='Search applicant profile by specified campaign id')

        parser.add_argument('--lookup',
            dest='lookup_field',
            choices=self.lookup_fields,
            default="yandex_id",
            help='Lookup for applicant instance by specified field and `campaign`')

        parser.add_argument('--skip',
            action="store_true",
            help='Skip dry mode and import data to DB')

        parser.add_argument('--passing_score', type=int,
            help='You can pass value to set `rejected by online test` '
                 'status for applicants below passing score')

        parser.add_argument('--contest_id', type=int,
            help='Save contest_id for easier debug. '
                 'Overrides `yandex_contest_id` field from source csv file')

    def handle(self, *args, **options):
        csv_path = options["csv"]
        lookup_field = options["lookup_field"]
        campaign_id = options["campaign_id"]
        if not campaign_id:
            raise CommandError("Campaign ID not specified")
        passing_score = options["passing_score"]
        dry_run = not options["skip"]
        contest_id = options["contest_id"]

        with open(csv_path, "rb") as f:
            data = tablib.Dataset().load(f.read())
            online_test_resource = OnlineTestRecordResource(
                lookup_field=lookup_field,
                allowed_fields=self.allowed_fields,
                campaign_id=campaign_id,
                passing_score=passing_score,
                contest_id=contest_id)
            result = online_test_resource.import_data(data, dry_run=dry_run)
            self.handle_errors(result)
            print("Done")

    @staticmethod
    def handle_errors(result):
        if result.has_errors():
            for error in result.base_errors:
                print(error)
            for line, errors in result.row_errors():
                for error in errors:
                    print("line {} - {}".format(line + 1, error.error))
