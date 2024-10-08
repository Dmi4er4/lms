from datetime import date

import pytest
from bs4 import BeautifulSoup
from django.conf import settings

from django.utils.encoding import smart_bytes

from core.models import Branch
from core.tests.factories import BranchFactory
from core.tests.settings import ANOTHER_DOMAIN
from core.urls import reverse
from courses.tests.factories import CourseFactory, SemesterFactory
from learning.settings import GradeTypes, StudentStatuses
from learning.tests.factories import EnrollmentFactory, GraduateProfileFactory
from projects.constants import ProjectGradeTypes
from projects.tests.factories import ProjectFactory
from users.tests.factories import CuratorFactory, StudentProfileFactory


@pytest.mark.django_db
def test_staff_diplomas_view(curator, client, settings):
    student_profile = StudentProfileFactory(status=StudentStatuses.WILL_GRADUATE)
    student = student_profile.user
    semester1 = SemesterFactory.create(year=2014, type="spring")
    p = ProjectFactory.create(students=[student], semester=semester1)
    sp = p.projectstudent_set.all()[0]
    sp.final_grade = ProjectGradeTypes.GOOD
    sp.save()
    client.login(curator)
    response = client.get(
        reverse(
            "staff:exports_future_graduates_diplomas_tex",
            kwargs={"branch_id": student_profile.branch_id},
        )
    )
    assert smart_bytes(p.name) in response.content


@pytest.mark.django_db
def test_staff_diplomas_view_should_contain_club_courses(curator, client, settings):
    student_profile = StudentProfileFactory(status=StudentStatuses.WILL_GRADUATE)
    student = student_profile.user

    # Add an enrollment to a club course, it should be shown in the TeX template
    branch_club = BranchFactory(site__domain=ANOTHER_DOMAIN)
    course_club = CourseFactory(
        main_branch=branch_club, branches=[student_profile.branch]
    )
    EnrollmentFactory(
        course=course_club,
        student=student,
        student_profile=student_profile,
        grade=GradeTypes.GOOD,
    )

    client.login(curator)
    response = client.get(
        reverse(
            "staff:exports_future_graduates_diplomas_tex",
            kwargs={"branch_id": student_profile.branch_id},
        )
    )
    assert smart_bytes(course_club.name) in response.content


@pytest.mark.django_db
def test_view_student_progress_report_full_download_csv(client):
    url = reverse(
        "staff:students_progress_report",
        kwargs={"output_format": "csv", "on_duplicate": "last"},
    )
    curator = CuratorFactory()
    client.login(curator)
    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"


@pytest.mark.django_db
def test_view_student_progress_report_for_term(client):
    curator = CuratorFactory()
    client.login(curator)
    term = SemesterFactory.create_current()
    url = reverse(
        "staff:students_progress_report_for_term",
        kwargs={"output_format": "csv", "term_type": term.type, "term_year": term.year},
    )
    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"


@pytest.mark.django_db
def test_view_student_faces_smoke(client):
    curator = CuratorFactory()
    client.login(curator)
    response = client.get(reverse("staff:student_faces"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_official_diplomas_list_view(client):
    # 2-digit day and month to avoid bothering with zero padding
    date1 = date(2020, 12, 20)
    date2 = date(2020, 11, 15)
    g1, g2 = GraduateProfileFactory.create_batch(2, diploma_issued_on=date1)
    g3 = GraduateProfileFactory(diploma_issued_on=date2)

    curator = CuratorFactory()
    client.login(curator)
    response = client.get(
        reverse(
            "staff:exports_official_diplomas_list",
            kwargs={"year": date1.year, "month": date1.month, "day": date1.day},
        )
    )

    def get_full_name(graduate_profile):
        return graduate_profile.student_profile.user.get_full_name(last_name_first=True)

    assert smart_bytes(get_full_name(g1)) in response.content
    assert smart_bytes(get_full_name(g2)) in response.content
    assert smart_bytes(get_full_name(g3)) not in response.content


@pytest.mark.django_db
def test_official_diplomas_views_should_be_site_aware(client, settings):
    # 2-digit day and month to avoid bothering with zero padding
    diploma_issued_on = date(2020, 12, 20)
    g1 = GraduateProfileFactory(
        student_profile__branch__site__domain=ANOTHER_DOMAIN,
        diploma_issued_on=diploma_issued_on,
    )

    # No graduates from current site, status codes should be 404
    curator = CuratorFactory()
    client.login(curator)
    response = client.get(
        reverse(
            "staff:exports_official_diplomas_list",
            kwargs={
                "year": diploma_issued_on.year,
                "month": diploma_issued_on.month,
                "day": diploma_issued_on.day,
            },
        )
    )
    assert response.status_code == 404

    response = client.get(
        reverse(
            "staff:exports_official_diplomas_csv",
            kwargs={
                "year": diploma_issued_on.year,
                "month": diploma_issued_on.month,
                "day": diploma_issued_on.day,
            },
        )
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_official_diplomas_list_should_be_sorted(client):
    # 2-digit day and month to avoid bothering with zero padding
    diploma_issued_on = date(2020, 12, 20)

    # Expected order after sorting: [g2, g1]
    g1 = GraduateProfileFactory(
        student_profile__user__last_name="Sidorov", diploma_issued_on=diploma_issued_on
    )
    g2 = GraduateProfileFactory(
        student_profile__user__last_name="Ivanov", diploma_issued_on=diploma_issued_on
    )

    curator = CuratorFactory()
    client.login(curator)
    response = client.get(
        reverse(
            "staff:exports_official_diplomas_list",
            kwargs={
                "year": diploma_issued_on.year,
                "month": diploma_issued_on.month,
                "day": diploma_issued_on.day,
            },
        )
    )

    soup = BeautifulSoup(response.content, "html.parser")
    user_links = [a["href"] for a in soup.select("div.container > ul > li > a")]
    assert user_links[-2] == g2.student_profile.user.get_absolute_url()
    assert user_links[-1] == g1.student_profile.user.get_absolute_url()


@pytest.mark.django_db
def test_official_diplomas_tex_should_not_contain_club_courses(client, settings):
    # 2-digit day and month to avoid bothering with zero padding
    diploma_issued_on = date(2020, 12, 20)
    g1 = GraduateProfileFactory(diploma_issued_on=diploma_issued_on)
    student_profile1 = g1.student_profile
    student1 = student_profile1.user

    course1 = CourseFactory(main_branch=student_profile1.branch)
    EnrollmentFactory(
        course=course1,
        student=student1,
        student_profile=student_profile1,
        grade=GradeTypes.GOOD,
    )

    # Add an enrollment to a club course, it should not be shown in the TeX template
    branch_club = BranchFactory(site__domain=ANOTHER_DOMAIN)
    course_club = CourseFactory(
        main_branch=branch_club, branches=[student_profile1.branch]
    )
    EnrollmentFactory(
        course=course_club,
        student=student1,
        student_profile=student_profile1,
        grade=GradeTypes.GOOD,
    )

    curator = CuratorFactory()
    client.login(curator)
    response = client.get(
        reverse(
            "staff:exports_official_diplomas_tex",
            kwargs={
                "year": diploma_issued_on.year,
                "month": diploma_issued_on.month,
                "day": diploma_issued_on.day,
            },
        )
    )

    assert smart_bytes(course1.name) in response.content
    assert smart_bytes(course_club.name) not in response.content
