# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import tablib
from dateutil import parser
from math import floor

from django.core.management import BaseCommand, CommandError
from django.utils import timezone
from django.utils.timezone import now

from learning.admission.models import Applicant, Exam, Interview, Comment, \
    Campaign
from learning.settings import PARTICIPANT_GROUPS
from users.models import CSCUser


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('csv', metavar='CSV',
                   help='path to csv with data')
        parser.add_argument('--year', type=int,
                            dest='campaign_year',
                            help='Campaign year')

    def handle(self, *args, **options):
        csv_path = options["csv"]
        campaign_year = options["campaign_year"]

        try:
            campaign = Campaign.objects.get(code=campaign_year)
        except Campaign.DoesNotExist:
            raise CommandError("Campaign not found")

        status_map = {
            "Берем": "accept",
            "ОтказЭкз": "rejected_exam",
            "ОтказСам": "they_refused",
            "ОтказСоб": "rejected_interview",
            "Не пришел": "rejected_exam",
            "НеПришел": "rejected_exam",
            "ЩАД": "rejected_interview",
            "Вольное слушание": "volunteer",
            "Иногородний": "rejected_interview",
            "Неактуально": "they_refused",
            "Списывание": "rejected_cheating",
        }

        reviewer_map = {
            "lilosea": 607,
            "andrey": 863,
            "kulikov": 5,
            "katya": 38,
            "nikita": 27,
            "ilya": 588,
            "avsmal": 32,
            "bliznets": 939,
        }

        dataset = tablib.Dataset().load(open(csv_path).read())
        for row in dataset.dict:
            try:
                applicant = Applicant.objects.get(
                    uuid=row['uuid'],
                    campaign=campaign
                )
            except Applicant.DoesNotExist:
                where_did_you_learn = []
                if row["habr"] == 'X':
                    where_did_you_learn.append("хабр")
                if row["friends"] == 'X':
                    where_did_you_learn.append("друзья")
                if row["tandp"] == 'X':
                    where_did_you_learn.append("tandp")
                if row["vk"] == 'X':
                    where_did_you_learn.append("vk")
                if row["club"] == 'X':
                    where_did_you_learn.append("клуб")
                if row["ad"] == 'X':
                    where_did_you_learn.append("ad")
                if row["other"] == 'X':
                    where_did_you_learn.append("другое")

                preferred_study_programs = []
                if row["cs"] == 'X':
                    preferred_study_programs.append("современная информатика")
                if row["dm"] == 'X':
                    preferred_study_programs.append("анализ данных")
                if row["se"] == 'X':
                    preferred_study_programs.append("разработка ПО")
                try:
                    created = parser.parse(row["created"])
                    created = timezone.make_aware(created,
                                                  timezone.get_current_timezone())
                except:
                    created = now()
                applicant = Applicant(
                    campaign=campaign,
                    created=created,
                    first_name=row["first_name"],
                    second_name=row["second_name"],
                    last_name=row["last_name"],
                    email=row["email"],
                    phone=row["phone"],
                    university=row["university"],
                    faculty="<empty>",
                    course=row["course"],
                    graduate_work=row["graduate_work"],
                    experience=row["experience"],
                    preferred_study_programs=", ".join(preferred_study_programs),
                    motivation=row["motivation"],
                    additional_info=row["additional_info"],
                    where_did_you_learn=", ".join(where_did_you_learn),
                    uuid=row["uuid"],
                )
            # set status

            applicant.status = status_map.get(row["interview_result"])

            applicant.save()
            # Set exam results
            try:
                exam = Exam.objects.get(applicant=applicant)
            except Exam.DoesNotExist:
                try:
                    score = floor(float(row["exam_score"]))
                except:
                    score = 0
                exam = Exam(
                    score=score,
                    applicant=applicant
                )
                exam.save()
            # Create interview
            if row["interview_date"]:
                interview_date = parser.parse(row["interview_date"])
                try:
                    hour, minute = row["interview_time"].split(":")
                    interview_date = interview_date.replace(
                        hour=int(hour), minute=int(minute)
                    )
                except:
                    pass
                interview_date = timezone.make_aware(interview_date,
                                                     timezone.get_current_timezone())
                reviewers = []
                for reviewer in reviewer_map:
                    try:
                        score = row[reviewer]
                        score = floor(float(score))
                        reviewers.append(reviewer)
                    except (TypeError, ValueError, KeyError):
                        pass

                try:
                    interview = Interview.objects.get(
                        date=interview_date,
                        status=Interview.COMPLETED,
                        applicant=applicant
                    )
                except Interview.DoesNotExist:
                    interview = Interview(
                        date=interview_date,
                        status=Interview.COMPLETED,
                        applicant=applicant,
                    )
                    interview.save()
                    interview.interviewers = [reviewer_map[x] for x in reviewers]
                    # Create comments
                    comment = None
                    for reviewer in reviewers:
                        reviewer_score = floor(float(row[reviewer]))

                        comment = Comment(
                            text="",
                            interview=interview,
                            interviewer_id=reviewer_map[reviewer],
                            score=floor(float(row[reviewer]))
                        )
                        comment.save()
                    # Append text to one of comment
                    if comment is not None:
                        comment.text = row["interview_comments"]
                        comment.save()

            if applicant.status in [Applicant.ACCEPT,
                                    Applicant.ACCEPT_IF,
                                    Applicant.VOLUNTEER]:
                try:
                    student = CSCUser.objects.get(
                        email=row["email"],
                        groups__in=[PARTICIPANT_GROUPS.STUDENT_CENTER,
                                    PARTICIPANT_GROUPS.GRADUATE_CENTER]
                    )
                    applicant.user = student
                    applicant.save()
                except:
                    pass

        print("Done")
