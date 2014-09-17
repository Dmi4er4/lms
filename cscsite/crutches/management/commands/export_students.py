# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import csv
import sys

from django.contrib.auth.models import Group
from django.core.management import BaseCommand

from learning.models import Semester
from users.models import CSCUser


class Command(BaseCommand):
    help = ("Exports all students along with courses "
            "they've enrolled on into a CSV file.")

    def handle(self, *args, **options):
        w = csv.writer(sys.stdout)

        current_semester = Semester.objects.latest()
        course_offerings = current_semester.courseoffering_set \
            .values_list("course__name", flat=True)
        course_offerings.sort()

        w.writerow(["ФИО", "Год поступления"] + course_offerings)

        student_group = Group.objects.get(pk=CSCUser.IS_STUDENT_PK)
        for student in student_group.user_set.all():
            enrolled_on = set(student.enrolled_on_set
                              .values_list("course__name", flat=True))

            row = [student.get_full_name(), student.enrollment_year]
            for course_offering in course_offerings:
                row.append(int(course_offering in enrolled_on))

            w.writerow(row)

        sys.stdout.flush()

