from django.db.models import OuterRef
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now

from core.db.expressions import SubqueryCount
from courses.models import Assignment, CourseNews, CourseTeacher, Course
from learning.models import AssignmentComment, AssignmentNotification, \
    StudentAssignment, Enrollment, CourseNewsNotification
from learning.settings import StudentStatuses


@receiver(post_save, sender=Enrollment)
def compute_course_learners_count(sender, instance: Enrollment, created,
                                  *args, **kwargs):
    if created and instance.is_deleted:
        return
    Course.objects.filter(id=instance.course_id).update(
        learners_count=SubqueryCount(
            Enrollment.active.filter(course_id=OuterRef('id'))
        )
    )


@receiver(post_save, sender=CourseNews)
def create_notifications_about_course_news(sender, instance: CourseNews,
                                           created, *args, **kwargs):
    if not created:
        return
    co_id = instance.course_id
    notifications = []
    active_enrollments = Enrollment.active.filter(course_id=co_id)
    for e in active_enrollments.iterator():
        notifications.append(
            CourseNewsNotification(user_id=e.student_id,
                                   course_offering_news_id=instance.pk))
    teachers = CourseTeacher.objects.filter(course_id=co_id)
    for co_t in teachers.iterator():
        notifications.append(
            CourseNewsNotification(user_id=co_t.teacher_id,
                                   course_offering_news_id=instance.pk))
    CourseNewsNotification.objects.bulk_create(notifications)


# TODO: send notification to other teachers
@receiver(post_save, sender=Assignment)
def create_student_assignments_for_new_assignment(sender, instance, created,
                                                  *args, **kwargs):
    if not created:
        return
    course = instance.course
    # Skip those who already been expelled
    active_students = (Enrollment.active
                       .filter(course=course)
                       .exclude(student__status=StudentStatuses.EXPELLED)
                       .values_list("student_id", flat=True))
    for student_id in active_students:
        a_s = StudentAssignment.objects.create(assignment=instance,
                                               student_id=student_id)
        # Note(Dmitry): we create notifications here instead of a separate
        #               receiver because it's much more efficient than getting
        #               StudentAssignment objects back one by one. It seems
        #               reasonable that 2*N INSERTs are better than bulk_create
        #               + N SELECTs + N INSERTs.
        # bulk_create doesn't return pks, that's the main reason
        (AssignmentNotification(user_id=student_id,
                                student_assignment=a_s,
                                is_about_creation=True)
         .save())


@receiver(post_save, sender=Assignment)
def create_deadline_change_notification(sender, instance, created,
                                        *args, **kwargs):
    if created:
        return
    if 'deadline_at' in instance.tracker.changed():
        active_enrollments = Enrollment.active.filter(course=instance.course)
        for e in active_enrollments:
            try:
                sa = (StudentAssignment.objects
                      .only('pk')
                      .get(student_id=e.student_id,
                           assignment=instance))
                (AssignmentNotification(user_id=e.student_id,
                                        student_assignment_id=sa.pk,
                                        is_about_deadline=True)
                 .save())
            except StudentAssignment.DoesNotExist:
                # It can occur when student was expelled
                continue


@receiver(post_save, sender=AssignmentComment)
def assignment_comment_post_save(sender, instance, created, *args, **kwargs):
    """
    Notify teachers if student leave a comment, otherwise notify student.
    Update `first_student_comment_at` and `last_comment_from`
    StudentAssignment model fields.

    Note:
        Can be essential for future signals but it doesn't update
        model attributes.
    """
    if not created:
        return

    comment = instance
    sa: StudentAssignment = comment.student_assignment
    notifications = []
    sa_update_dict = {"modified": now()}
    if comment.author_id == sa.student_id:
        other_comments = (sa.assignmentcomment_set
                          .filter(author_id=comment.author_id)
                          .exclude(pk=comment.pk))
        is_first_comment = not other_comments.exists()
        is_about_passed = sa.assignment.is_online and is_first_comment

        teachers = comment.student_assignment.assignment.notify_teachers.all()
        for t in teachers:
            notifications.append(
                AssignmentNotification(user_id=t.teacher_id,
                                       student_assignment=sa,
                                       is_about_passed=is_about_passed))

        if is_first_comment:
            sa_update_dict["first_student_comment_at"] = comment.created
        sa_update_dict["last_comment_from"] = sa.CommentAuthorTypes.STUDENT
    else:
        sa_update_dict["last_comment_from"] = sa.CommentAuthorTypes.TEACHER
        student_id = comment.student_assignment.student_id
        notifications.append(
            AssignmentNotification(user_id=student_id, student_assignment=sa)
        )
    AssignmentNotification.objects.bulk_create(notifications)
    sa.__class__.objects.filter(pk=sa.pk).update(**sa_update_dict)
    for attr_name in sa_update_dict:
        setattr(sa, attr_name, sa_update_dict[attr_name])
