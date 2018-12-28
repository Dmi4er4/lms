import logging
from typing import List, Optional

from django.db.models import Case, Count, Value, When, \
    IntegerField, Prefetch
from django.urls import reverse
from django.utils.translation import ugettext_noop

from core.utils import is_club_site
from courses.models import Assignment
from courses.tabs import CourseTab, CourseTabPanel
from courses.tabs_registry import register
from learning.permissions import course_access_role, CourseRole

logger = logging.getLogger(__name__)


@register
class CourseContactsTab(CourseTab):
    type = 'contacts'
    title = ugettext_noop("CourseTab|Contacts")
    priority = 20
    is_hidden = False

    @classmethod
    def is_enabled(cls, course, user=None):
        return user.get_enrollment(course.pk) or user.is_curator

    def get_tab_panel(self, **kwargs) -> Optional[CourseTabPanel]:
        return CourseTabPanel(context={"items": get_course_contacts(**kwargs)})


@register
class CourseNewsTab(CourseTab):
    type = 'news'
    title = ugettext_noop("CourseTab|News")
    priority = 60

    @classmethod
    def is_enabled(cls, course, user=None):
        if is_club_site():
            return True
        role = course_access_role(course=course, request_user=user)
        return role != CourseRole.NO_ROLE and role != CourseRole.STUDENT_RESTRICT

    def get_tab_panel(self, **kwargs) -> Optional[CourseTabPanel]:
        return CourseTabPanel(context={"items": get_course_news(**kwargs)})


@register
class CourseReviewsTab(CourseTab):
    type = 'reviews'
    title = ugettext_noop("CourseTab|Reviews")
    priority = 30
    is_hidden = False

    @classmethod
    def is_enabled(cls, course, user=None):
        return course.enrollment_is_open and (user.is_student or user.is_curator)

    def get_tab_panel(self, **kwargs) -> Optional[CourseTabPanel]:
        return CourseTabPanel(context={"items": get_course_reviews(**kwargs)})


@register
class CourseAssignmentsTab(CourseTab):
    type = 'assignments'
    title = ugettext_noop("CourseTab|Assignments")
    priority = 50

    @classmethod
    def is_enabled(cls, course, user=None):
        return (user.is_student or user.is_graduate or user.is_curator or
                user.is_teacher or user.get_enrollment(course.pk))

    def get_tab_panel(self, **kwargs) -> Optional[CourseTabPanel]:
        return CourseTabPanel(context={
            "items": get_course_assignments(**kwargs)
        })


def get_course_news(course, **kwargs):
    return course.coursenews_set.all()


def get_course_reviews(course, **kwargs):
    return course.enrollment_is_open and course.get_reviews()


def get_course_assignments(course, user, user_role=None) -> List[Assignment]:
    """
    For enrolled students show links to there submissions.
    Course teachers (among all terms) see links to assignment details.
    Others can see only assignment names.
    """
    if user_role is None:
        user_role = course_access_role(course=course, request_user=user)
    Assignment = course.assignment_set.field.model
    AssignmentAttachment = Assignment.assignmentattachment_set.field.model
    attachments = Prefetch("assignmentattachment_set",
                           queryset=AssignmentAttachment.objects.order_by())
    assignments = (course.assignment_set
                   .only("title", "course_id", "is_online", "deadline_at")
                   .prefetch_related(attachments)
                   .order_by('deadline_at', 'title'))
    student_roles = (CourseRole.STUDENT_REGULAR,
                     CourseRole.STUDENT_RESTRICT)
    if user_role in student_roles:
        assignments = assignments.prefetch_student_scores(user)
    assignments = assignments.all()  # enable query caching
    for a in assignments:
        to_details = None
        if user_role in student_roles:
            assignment_progress = a.studentassignment_set.first()
            if assignment_progress is not None:
                if user_role == CourseRole.STUDENT_RESTRICT:
                    # Hide the link if student didn't send any comment on
                    # assignment (first comment is considered as a solution)
                    if not assignment_progress.student_comments_cnt:
                        continue
                to_details = assignment_progress.get_student_url()
            else:
                logger.info(f"no StudentAssignment for student ID "
                            f"{user.pk}, assignment ID {a.pk}")
        elif user_role in [CourseRole.TEACHER, CourseRole.CURATOR]:
            to_details = reverse("assignment_detail_teacher", args=[a.pk])
        setattr(a, 'magic_link', to_details)
    return assignments


def get_course_contacts(course, **kwargs):
    teachers_by_role = course.get_grouped_teachers()
    return [ct for g in teachers_by_role.values() for ct in g
            if len(ct.teacher.private_contacts.strip()) > 0]