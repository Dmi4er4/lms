import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Case, Count, F, IntegerField, When, Window
from django.utils.timezone import now

from core.timezone import get_now_utc
from courses.models import CourseTeacher
from grading.services import CheckerSubmissionService
from learning.models import (
    AssignmentComment, AssignmentScoreAuditLog, AssignmentSubmissionTypes, Enrollment,
    PersonalAssignmentActivity, StudentAssignment
)
from learning.services import StudentGroupService
from learning.settings import AssignmentScoreUpdateSource
from users.models import User

logger = logging.getLogger(__name__)


def update_personal_assignment_stats(*, personal_assignment: StudentAssignment) -> None:
    """
    Calculates and fully replaces personal assignment stats stored
    in a `stats` property of the .meta json field.
    """
    solutions_count = Count(
        Case(When(type=AssignmentSubmissionTypes.SOLUTION,
                  then=1),
             output_field=IntegerField()))
    window = {
        'partition_by': [F('student_assignment_id')],
        'order_by': F('created').asc()
    }
    latest_submission = (AssignmentComment.published
                         .filter(student_assignment_id=personal_assignment.pk)
                         .annotate(comments_total=Window(expression=Count('*'), **window),
                                   solutions_total=Window(expression=solutions_count, **window))
                         .order_by('created')
                         .last())
    if latest_submission is None:
        return

    if latest_submission.type == AssignmentSubmissionTypes.SOLUTION:
        latest_activity = PersonalAssignmentActivity.SOLUTION
    elif latest_submission.type == AssignmentSubmissionTypes.COMMENT:
        is_student = latest_submission.author_id == personal_assignment.student_id
        if is_student:
            latest_activity = PersonalAssignmentActivity.STUDENT_COMMENT
        else:
            latest_activity = PersonalAssignmentActivity.TEACHER_COMMENT
    else:
        raise ValueError('Unknown submission type')
    # Django 3.2 doesn't support partial update of the json field,
    # better to select_for_update
    meta = personal_assignment.meta or {}
    stats = {
        'comments': latest_submission.comments_total,
        'activity': {
            'code': str(latest_activity),
            'dt': latest_submission.created.replace(microsecond=0)
        }
    }
    # Omit default or null values to save space
    if latest_submission.solutions_total:
        stats['solutions'] = latest_submission.solutions_total
    meta['stats'] = stats
    (StudentAssignment.objects
     .filter(pk=personal_assignment.pk)
     .update(meta=meta))


def create_assignment_solution(*, personal_assignment: StudentAssignment,
                               created_by: User,
                               execution_time: Optional[timedelta] = None,
                               message: Optional[str] = None,
                               attachment: Optional[UploadedFile] = None) -> AssignmentComment:
    if not message and not attachment:
        raise ValidationError("Provide either text or a file.", code="malformed")

    solution = AssignmentComment(student_assignment=personal_assignment,
                                 author=created_by,
                                 type=AssignmentSubmissionTypes.SOLUTION,
                                 is_published=True,
                                 execution_time=execution_time,
                                 text=message,
                                 attached_file=attachment)
    solution.save()

    from learning.tasks import update_student_assignment_stats
    update_student_assignment_stats.delay(personal_assignment.pk)

    return solution


# TODO: Looks like a good example for signal (save additional checker settings
#  to the StudentAssignment.meta, then move checker part to the grading app?)
def create_assignment_solution_and_check(*, personal_assignment: StudentAssignment,
                                         created_by: User, settings: Dict[str, Any],
                                         execution_time: Optional[timedelta] = None,
                                         attachment: Optional[UploadedFile] = None) -> AssignmentComment:
    """Creates assignment solution along with a checker submission."""
    solution = create_assignment_solution(personal_assignment=personal_assignment,
                                          created_by=created_by, execution_time=execution_time,
                                          message='', attachment=attachment)
    CheckerSubmissionService.update_or_create(solution, **settings)
    return solution


def create_assignment_comment(*, personal_assignment: StudentAssignment,
                              is_draft: bool, created_by: User,
                              message: Optional[str] = None,
                              attachment: Optional[UploadedFile] = None) -> AssignmentComment:
    if not message and not attachment:
        raise ValidationError("Provide either text or a file.", code="malformed")

    comment = get_draft_comment(created_by, personal_assignment)
    if comment is None:
        comment = AssignmentComment(student_assignment=personal_assignment,
                                    author=created_by,
                                    type=AssignmentSubmissionTypes.COMMENT)
    comment.is_published = not is_draft
    comment.text = message
    comment.attached_file = attachment
    comment.created = get_now_utc()  # TODO: write test
    comment.save()

    from learning.tasks import update_student_assignment_stats
    update_student_assignment_stats.delay(personal_assignment.pk)

    return comment


def get_draft_submission(user: User,
                         student_assignment: StudentAssignment,
                         submission_type) -> Optional[AssignmentComment]:
    """Returns draft submission if it was previously saved."""
    return (AssignmentComment.objects
            .filter(author=user,
                    is_published=False,
                    type=submission_type,
                    student_assignment=student_assignment)
            .order_by('pk')
            .last())


def get_draft_comment(user: User, student_assignment: StudentAssignment):
    return get_draft_submission(user, student_assignment,
                                AssignmentSubmissionTypes.COMMENT)


def get_draft_solution(user: User, student_assignment: StudentAssignment):
    return get_draft_submission(user, student_assignment,
                                AssignmentSubmissionTypes.SOLUTION)


def update_personal_assignment_score(*, student_assignment: StudentAssignment,
                                     changed_by: User, score_old: Decimal, score_new: Decimal,
                                     source: AssignmentScoreUpdateSource) -> StudentAssignment:
    if score_new is not None and score_new > student_assignment.assignment.maximum_score:
        raise ValueError("Score value is greater than the maximum score")
    student_assignment.score = score_new
    student_assignment.save(update_fields=['score'])

    audit_log = AssignmentScoreAuditLog(student_assignment=student_assignment,
                                        changed_by=changed_by,
                                        score_old=score_old,
                                        score_new=score_new,
                                        source=source)
    audit_log.save()

    return student_assignment


# TODO: remove
def update_student_assignment_derivable_fields(comment):
    """
    Optimize db queries by reimplementing next logic:
        student_assignment.compute_fields('first_student_comment_at')
    """
    if not comment.pk:
        return
    sa: StudentAssignment = comment.student_assignment
    fields = {"modified": now()}
    if comment.author_id == sa.student_id:
        # FIXME: includes solutions. is it ok?
        other_comments = (sa.assignmentcomment_set(manager='published')
                          .filter(author_id=comment.author_id)
                          .exclude(pk=comment.pk))
        is_first_comment = not other_comments.exists()
        if is_first_comment:
            fields["first_student_comment_at"] = comment.created
    StudentAssignment.objects.filter(pk=sa.pk).update(**fields)
    for attr_name, attr_value in fields.items():
        setattr(sa, attr_name, attr_value)


def resolve_assignees_for_personal_assignment(student_assignment: StudentAssignment) -> List[CourseTeacher]:
    if student_assignment.assignee is not None:
        return [student_assignment.assignee]

    assignment = student_assignment.assignment
    try:
        enrollment = (Enrollment.active
                      .select_related('student_group')
                      .get(course_id=assignment.course_id,
                           student_id=student_assignment.student_id))
    except Enrollment.DoesNotExist:
        # No need to search for the candidates
        logger.info(f"User {student_assignment.student_id} left the course.")
        raise
    return StudentGroupService.get_assignees(enrollment.student_group, assignment)


def maybe_set_assignee_for_personal_assignment(submission: AssignmentComment) -> None:
    """
    Auto assign teacher in a lazy manner (on student activity) when
    student group has assignee.
    """
    student_assignment = submission.student_assignment
    # Trigger on student activity
    if submission.author_id != student_assignment.student_id:
        return None
    if not student_assignment.trigger_auto_assign:
        return None
    update_fields = ['trigger_auto_assign', 'modified']
    # Do not overwrite assignee if someone already set the value.
    if not student_assignment.assignee_id:
        try:
            assignees = resolve_assignees_for_personal_assignment(student_assignment)
        except Enrollment.DoesNotExist:
            # Left auto assigning trigger until student re-enter the course.
            return None
        if assignees:
            if len(assignees) == 1:
                update_fields.append('assignee')
                assignee = assignees[0]
                student_assignment.assignee = assignee
            else:
                # It is unclear who must be set as an assignee in that case.
                # Let's leave it blank to send notifications to all responsible
                # teachers until they decide who must be assigned.
                # TODO: set all of them as watchers instead
                pass
    student_assignment.trigger_auto_assign = False
    student_assignment.modified = now()
    student_assignment.save(update_fields=update_fields)