from collections import OrderedDict
from typing import Union
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext_lazy as _
from django.views import generic
from django.views.generic.edit import BaseUpdateView
from vanilla import TemplateView

from core.exceptions import Redirect
from core.settings.base import FOUNDATION_YEAR
from core.timezone import Timezone, CityCode
from core.urls import reverse
from core.utils import render_markdown, is_club_site
from courses.calendar import CalendarEvent
from courses.models import CourseClass, Course, Assignment
from courses.settings import SemesterTypes
from courses.utils import get_terms_for_calendar_month, get_term_index, \
    get_current_term_pair
from courses.views.calendar import MonthEventsCalendarView
from courses.views.mixins import CourseURLParamsMixin
from learning.calendar import get_month_events
from learning.forms import AssignmentModalCommentForm, AssignmentScoreForm
from learning.gradebook.views import GradeBookListBaseView
from learning.models import AssignmentComment, StudentAssignment, Enrollment
from learning.permissions import course_access_role, CourseRole
from learning.views import AssignmentSubmissionBaseView
from learning.views.views import logger
from users.mixins import TeacherOnlyMixin
from users.utils import get_teacher_city_code


# Note: Wow, looks like a shit
class AssignmentListView(TeacherOnlyMixin, TemplateView):
    model = StudentAssignment
    context_object_name = 'student_assignment_list'
    template_name = "learning/teaching/assignment_list.html"
    user_type = 'teacher'

    filter_by_score = (
        ("any", _("All")),  # Default
        ("no", _("Without score")),
        ("yes", _("With grade")),
    )
    filter_by_comments = (
        ("any", _("No matter")),
        ("student", _("From student")),
        ("teacher", _("From teacher")),
        ("empty", _("Without comments")),
    )

    def get_queryset(self, filters):
        # TODO: Show cs center courses on club site?
        return (
            StudentAssignment.objects
            .filter(**filters)
            .select_related("assignment", "student",)
            .only("id",
                  "score",
                  "first_student_comment_at",
                  "student__first_name",
                  "student__last_name",
                  "assignment__id",
                  "assignment__course_id",
                  "assignment__is_online",
                  "assignment__passing_score",
                  "assignment__maximum_score",)
            .prefetch_related("student__groups",)
            .order_by('student__last_name', 'student__first_name'))

    def get_context_data(self, **kwargs):
        context = {
            "filter_by_score": self.filter_by_score,
            "filter_by_comments": self.filter_by_comments
        }
        filters = self.prepare_queryset_filters(context)
        if "assignment" in filters:
            course_id = filters["assignment"].course_id
            # TODO: select `deleted` instead?
            # TODO: move to separated method and return set
            qs = (Enrollment.active
                  .filter(course_id=course_id)
                  .values_list("student_id", flat=True))
            context["enrollments"] = set(qs)
        context["student_assignment_list"] = self.get_queryset(filters)
        # Url for assignment filter
        query_tuple = [
            ('term', self.query["term"]),
            ('course', self.query["course_slug"]),
            ('score', self.query["score"]),
            ('comment', self.query["comment"]),
            ('assignment', ""),  # should be the last one
        ]
        self.query["form_url"] = "{}?{}".format(
            reverse("teaching:assignment_list"),
            urlencode(OrderedDict(query_tuple))
        )
        context["query"] = self.query
        return context

    def prepare_queryset_filters(self, context):
        """
        We process GET-query in optimistic way - assume that invalid data
        comes very rarely.
        Processing order of GET-params:
            term -> course -> assignment -> score -> comment
        If query value invalid -> redirect to entry page.
        Also, we collect data for filter widgets.

        1. Get all courses for authenticated user (we should fallback to
        previous term if no readings in current term)
        2. Collect all available terms (used in filter widget)
        3. Get term by `term` GET-param if valid or the latest one from step 2.
        4. Get courses for resulting term (used in filter widget)
        5. Get course offering by `course` GET-param if valid or get one from
        list of courses for resulting term (step 4)
        6. Collect assignments for resulting course (used in filter)
        7. Get assignment by `assignment` GET-param or latest from step 6.
        8. Set filters by resulting assignment, score and last comment.
        """
        filters = {}
        teacher_all_courses = self._get_all_teacher_courses()
        all_terms = set(c.semester for c in teacher_all_courses)
        all_terms = sorted(all_terms, key=lambda t: -t.index)
        # Try to get course offerings for requested term
        query_term_index = self._get_requested_term_index(all_terms)
        course_offerings = [c for c in teacher_all_courses
                            if c.semester.index == query_term_index]
        # Try to get assignments for requested course
        query_co = self._get_requested_course(course_offerings)
        # FIXME: attach course or pass it to deadline_at_local
        assignments = list(
            Assignment.objects
            .filter(notify_teachers__teacher=self.request.user,
                    course=query_co)
            .only("pk", "deadline_at", "title", "course_id")
            .order_by("-deadline_at"))
        query_assignment = self._get_requested_assignment(assignments)
        if query_assignment:
            filters["assignment"] = query_assignment
        # Set filter by score
        query_score, filter_name, filter_value = self._get_filter_by_score()
        if filter_name:
            filters[filter_name] = filter_value
        # Set filter by comment
        query_comment, filter_name, filter_value = self._get_filter_by_status()
        if filter_name:
            filters[filter_name] = filter_value

        # Cache to avoid additional queries to DB
        context["all_terms"] = all_terms
        context["course_offerings"] = course_offerings
        context["assignments"] = assignments
        self.query = {
            "course_slug": query_co.meta_course.slug,
            "term": query_co.semester.slug,
            "assignment": query_assignment,
            "score": query_score,
            "comment": query_comment
        }
        return filters

    def _get_filter_by_score(self):
        filter_name, filter_value = None, None
        query_value = self.request.GET.get("score", "any")
        # FIXME: validate GET-params in separated method? and redirect?
        if query_value not in (k for k, v in self.filter_by_score):
            query_value = "any"
        if query_value == "no":
            filter_name, filter_value = "score__isnull", True
        elif query_value == "yes":
            filter_name, filter_value = "score__isnull", False
        # FIXME: Может не устанавливать его вообще :<
        return query_value, filter_name, filter_value

    def _get_filter_by_status(self):
        filter_name, filter_value = None, None
        query_value = self.request.GET.get("comment", "any")
        if query_value not in (k for k, v in self.filter_by_comments):
            query_value = "any"
        if query_value == "student":
            filter_name = "last_comment_from"
            filter_value = self.model.CommentAuthorTypes.STUDENT
        elif query_value == "teacher":
            filter_name = "last_comment_from"
            filter_value = self.model.CommentAuthorTypes.TEACHER
        elif query_value == "empty":
            filter_name = "last_comment_from"
            filter_value = self.model.CommentAuthorTypes.NOBODY
        return query_value, filter_name, filter_value

    def _get_all_teacher_courses(self):
        """Returns all courses for authenticated teacher"""
        u = self.request.user
        cs = (Course.objects
              .filter(teachers=u)
              .select_related("meta_course", "semester")
              .order_by("semester__index", "meta_course__name"))
        if not cs:
            logger.warning(f"Teacher {u} has not conducted any course")
            self._redirect_to_course_list()
        return cs

    def _get_requested_term_index(self, all_terms):
        """
        Calculate term index from `term` and `year` GET-params.
        If term index not presented in teachers term_list, redirect
        to the latest available valid term from this list.
        """
        assert len(all_terms) > 0
        query_term = self.request.GET.get("term")
        if not query_term:
            # Terms in descending order, choose the latest one
            return all_terms[0].index
        try:
            year, term_type = query_term.split("-")
            year = int(year)
            if year < FOUNDATION_YEAR:  # invalid GET-param value
                raise ValidationError("Wrong year value")
            if term_type not in SemesterTypes.values:
                raise ValidationError("Wrong term type")
            term = next((t for t in all_terms if
                         t.type == term_type and t.year == year), None)
            if not term:
                raise ValidationError("Term not presented among available")
        except (ValueError, ValidationError):
            raise Redirect(to=reverse("teaching:assignment_list"))
        return term.index

    def _get_requested_course(self, courses):
        assert len(courses) > 0
        """Get requested course by GET-param `course`"""
        course_slug = self.request.GET.get("course", "")
        try:
            co = next(c for c in courses if c.meta_course.slug == course_slug)
        except StopIteration:
            # TODO: get term and redirect to entry page
            co = courses[0]
        return co

    def _get_requested_assignment(self, assignments):
        try:
            assignment_id = int(self.request.GET.get("assignment", ""))
        except ValueError:
            # FIXME: Ищем ближайшее, где должен наступить дедлайн
            assignment_id = next((a.pk for a in assignments), False)
        return next((a for a in assignments if a.pk == assignment_id),
                    None)

    def _redirect_to_course_list(self):
        messages.info(self.request,
                      _("You were redirected from Assignments due to "
                        "empty course list."),
                      extra_tags='timeout')
        raise Redirect(to=reverse("teaching:course_list"))


class TimetableView(TeacherOnlyMixin, MonthEventsCalendarView):
    """
    Shows classes for courses where authorized teacher participate in.
    """
    calendar_type = "teacher"
    template_name = "learning/teaching/timetable.html"

    def get_default_timezone(self):
        return get_teacher_city_code(self.request)

    def get_events(self, year, month, **kwargs):
        qs = (CourseClass.objects
              .for_timetable()
              .in_month(year, month)
              .filter(course__teachers=self.request.user))
        return (CalendarEvent(e) for e in qs)


class CalendarFullView(TeacherOnlyMixin, MonthEventsCalendarView):
    """
    Shows all non-course events and classes filtered by the cities where
    authorized teacher has taught.
    """

    def get_default_timezone(self) -> Union[Timezone, CityCode]:
        return get_teacher_city_code(self.request)

    def get_teacher_cities(self, year, month):
        default_city = get_teacher_city_code(self.request)
        if is_club_site():
            return [default_city]
        # Collect all the cities where authorized teacher taught.
        terms_in_month = get_terms_for_calendar_month(year, month)
        term_indexes = [get_term_index(*term) for term in terms_in_month]
        cities = list(Course.objects
                      .filter(semester__index__in=term_indexes)
                      .for_teacher(self.request.user)
                      .values_list("city_id", flat=True)
                      .order_by('city_id')
                      .distinct())
        if not cities:
            cities = [default_city]
        return cities

    def get_events(self, year, month, **kwargs):
        cities = self.get_teacher_cities(year, month)
        return get_month_events(year, month, cities)


class CalendarPersonalView(CalendarFullView):
    """
    Shows all non-course events and classes for courses in which authenticated
    teacher participated.
    """
    calendar_type = 'teacher'
    template_name = "learning/calendar.html"

    def get_events(self, year, month, **kwargs):
        cities = self.get_teacher_cities(year, month)
        return get_month_events(year, month, cities,
                                for_teacher=self.request.user)


class CourseListView(TeacherOnlyMixin, generic.ListView):
    model = Course
    context_object_name = 'course_list'
    template_name = "learning/teaching/course_list.html"

    def get_queryset(self):
        return (Course.objects
                .filter(teachers=self.request.user)
                .select_related('meta_course', 'semester')
                .prefetch_related('teachers')
                .order_by('-semester__index', 'meta_course__name'))


class CourseStudentsView(TeacherOnlyMixin, CourseURLParamsMixin, TemplateView):
    # raise_exception = True
    template_name = "learning/teaching/course_students.html"

    def handle_no_permission(self, request):
        raise Http404

    def get_context_data(self, **kwargs):
        co = get_object_or_404(self.get_course_queryset())
        return {
            "co": co,
            "enrollments": (co.enrollment_set(manager="active")
                            .select_related("student"))
        }


# TODO: add permissions tests! Or perhaps anyone can look outside comments if I missed something :<
# FIXME: replace with vanilla view
class AssignmentCommentUpdateView(generic.UpdateView):
    model = AssignmentComment
    pk_url_kwarg = 'comment_pk'
    context_object_name = "comment"
    template_name = "learning/teaching/modal_update_assignment_comment.html"
    form_class = AssignmentModalCommentForm

    def form_valid(self, form):
        self.object = form.save()
        html = render_markdown(self.object.text)
        return JsonResponse({"success": 1,
                             "id": self.object.pk,
                             "html": html})

    def form_invalid(self, form):
        return JsonResponse({"success": 0, "errors": form.errors})

    def check_permissions(self, comment):
        # Allow view/edit own comments to teachers and all to curators
        if not self.request.user.is_curator:
            is_teacher = self.request.user.is_teacher
            if comment.author_id != self.request.user.pk or not is_teacher:
                raise PermissionDenied
            # Check comment not in stale state for edit
            if comment.is_stale_for_edit():
                raise PermissionDenied

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.check_permissions(self.object)
        return super(BaseUpdateView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.check_permissions(self.object)
        return super(BaseUpdateView, self).post(request, *args, **kwargs)


class AssignmentDetailView(TeacherOnlyMixin, generic.DetailView):
    model = Assignment
    template_name = "learning/teaching/assignment_detail.html"
    context_object_name = 'assignment'

    def get_queryset(self):
        return (Assignment.objects
                .select_related('course',
                                'course__meta_course',
                                'course__semester')
                .prefetch_related('assignmentattachment_set'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role = course_access_role(course=self.object.course,
                                  user=self.request.user)
        if role not in [CourseRole.CURATOR, CourseRole.TEACHER]:
            raise PermissionDenied
        context['a_s_list'] = (
            StudentAssignment.objects
            .filter(assignment__pk=self.object.pk)
            .select_related('assignment',
                            'assignment__course',
                            'assignment__course__meta_course',
                            'assignment__course__semester',
                            'student')
            .prefetch_related('student__groups'))
        return context


class StudentAssignmentDetailView(TeacherOnlyMixin,
                                  AssignmentSubmissionBaseView):
    template_name = "learning/teaching/student_assignment_detail.html"

    def has_access(self, user, student_assignment):
        role = course_access_role(course=student_assignment.assignment.course,
                                  user=user)
        return role in (CourseRole.TEACHER, CourseRole.CURATOR)

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form, **kwargs)
        user = self.request.user
        a_s = self.student_assignment
        course = a_s.assignment.course
        # Get next unchecked assignment
        # FIXME: next student assignment mb?
        base = (StudentAssignment.objects
                .filter(score__isnull=True,
                        first_student_comment_at__isnull=False,
                        assignment__course=course,
                        assignment__course__teachers=user)
                .order_by('assignment__deadline_at', 'pk')
                .only('pk'))
        next_student_assignment = (base.filter(pk__gt=a_s.pk).first() or
                                   base.filter(pk__lt=a_s.pk).first())
        context['next_student_assignment'] = next_student_assignment
        context['is_actual_teacher'] = user in course.teachers.all()
        context['score_form'] = AssignmentScoreForm(
            initial={'score': a_s.score},
            maximum_score=a_s.assignment.maximum_score)
        return context

    def post(self, request, *args, **kwargs):
        # TODO: separated update view
        if 'grading_form' in request.POST:
            a_s = self.student_assignment
            form = AssignmentScoreForm(request.POST,
                                       maximum_score=a_s.assignment.maximum_score)

            # Too hard to use ProtectedFormMixin here, let's just inline it's
            # logic. A little drawback is that teachers still can leave
            # comments under other's teachers assignments, but can not grade,
            # so it's acceptable, IMO.
            teachers = a_s.assignment.course.teachers.all()
            if request.user not in teachers:
                raise PermissionDenied

            if form.is_valid():
                a_s.score = form.cleaned_data['score']
                a_s.save()
                if a_s.score is None:
                    messages.info(self.request,
                                  _("Score was deleted"),
                                  extra_tags='timeout')
                else:
                    messages.success(self.request,
                                     _("Score successfully saved"),
                                     extra_tags='timeout')
                return redirect(a_s.get_teacher_url())
            else:
                # not sure if we can do anything more meaningful here.
                # it shouldn't happen, after all.
                return HttpResponseBadRequest(_("Grading form is invalid") +
                                              "{}".format(form.errors))
        else:
            return super().post(request, *args, **kwargs)

    def get_success_url(self):
        return self.student_assignment.get_teacher_url()


class GradeBookListView(TeacherOnlyMixin, GradeBookListBaseView):
    template_name = "learning/teaching/gradebook_list.html"

    def get_course_queryset(self):
        qs = super().get_course_queryset()
        return qs.filter(teachers=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # FIXME: Is it ok to use 'spb' here?
        current_year, term_type = get_current_term_pair('spb')
        current_term_index = get_term_index(current_year, term_type)
        co_count = 0
        # Redirect teacher to the appropriate gradebook page if he has only
        # one course in the current semester.
        for semester in context["semester_list"]:
            if semester.index == current_term_index:
                if len(semester.courseofferings) == 1:
                    co = semester.courseofferings[0]
                    raise Redirect(to=co.get_gradebook_url())
            co_count += len(semester.courseofferings)
        if not co_count:
            context["semester_list"] = []
        return context