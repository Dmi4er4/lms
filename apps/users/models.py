import base64
import logging
from random import choice
from string import ascii_lowercase, digits
from typing import Optional

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser, PermissionsMixin, \
    _user_has_perm
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import RegexValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.encoding import smart_text
from django.utils.functional import cached_property
from django.utils.text import normalize_newlines
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField
from model_utils.fields import MonitorField, AutoLastModifiedField
from model_utils.models import TimeStampedModel
from sorl.thumbnail import ImageField

from auth.permissions import all_permissions
from compscicenter_ru.utils import PublicRoute
from core.models import LATEX_MARKDOWN_ENABLED, City
from core.urls import reverse
from core.utils import is_club_site, ru_en_mapping
from courses.models import Semester
from learning.permissions import LearningPermissionsMixin
from learning.settings import StudentStatuses, GradeTypes, AcademicDegreeYears
from learning.utils import is_negative_grade
from users.constants import GROUPS_IMPORT_TO_GERRIT, Roles, \
    SHADCourseGradeTypes, GenderTypes
from users.fields import MonitorStatusField
from auth.tasks import update_password_in_gerrit
from users.thumbnails import UserThumbnailMixin
from .managers import CustomUserManager

# See 'https://help.yandex.ru/pdd/additional/mailbox-alias.xml'.
YANDEX_DOMAINS = ["yandex.ru", "narod.ru", "yandex.ua",
                  "yandex.by", "yandex.kz", "ya.ru", "yandex.com"]


logger = logging.getLogger(__name__)

# Github username may only contain alphanumeric characters or
# single hyphens, and cannot begin or end with a hyphen
GITHUB_LOGIN_VALIDATOR = RegexValidator(regex="^[a-zA-Z0-9](-?[a-zA-Z0-9])*$")


# FIXME: rename to student status log and move to learning app (and all User.status* fields to StudentProfile)
class UserStatusLog(models.Model):
    created = models.DateField(_("created"), default=now)
    semester = models.ForeignKey(
        "courses.Semester",
        verbose_name=_("Semester"),
        on_delete=models.CASCADE)
    status = models.CharField(
        choices=StudentStatuses.choices,
        verbose_name=_("Status"),
        max_length=15)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Student"),
        on_delete=models.CASCADE)

    class Meta:
        ordering = ['-pk']

    def prepare_fields(self, monitored_instance, monitoring_field_attname):
        if not self.student_id:
            self.student_id = monitored_instance.pk
        # Prevent additional queries in admin
        if not self.semester_id:
            self.semester_id = Semester.get_current().pk

    def __str__(self):
        return smart_text("{} [{}]".format(
            self.student.get_full_name(True), self.semester))


class ExtendedAnonymousUser(LearningPermissionsMixin, AnonymousUser):
    city_code = None
    index_redirect = None
    roles = set()

    def __str__(self):
        return 'ExtendedAnonymousUser'

    def get_enrollment(self, course_id: int) -> Optional["Enrollment"]:
        return None


class Group(models.Model):
    """
    Groups are a generic way of categorizing users to apply some label.
    A user can belong to any number of groups.

    Groups are a convenient way to categorize users to
    apply some label, or extended functionality, to them. For example, you
    could create a group 'Special users', and you could write code that would
    do special things to those users -- such as giving them access to a
    members-only portion of your site, or sending them members-only email
    messages.
    """
    name = models.CharField(_('name'), max_length=150, unique=True)

    class Meta:
        verbose_name = _('group')
        verbose_name_plural = _('groups')

    def __str__(self):
        return self.name

    def natural_key(self):
        return self.name,


def get_current_site():
    return settings.SITE_ID


class UserGroup(models.Model):
    """Maps users to site and groups. Used by users.groups.AccessGroup."""

    user = models.ForeignKey('users.User', verbose_name=_("User"),
                             on_delete=models.CASCADE,
                             related_name="groups",
                             related_query_name="group")
    site = models.ForeignKey('sites.Site', verbose_name=_("Site"),
                             db_index=False,
                             on_delete=models.PROTECT,
                             default=get_current_site)
    role = models.PositiveSmallIntegerField(_("Role"),
                                            choices=Roles.choices)

    class Meta:
        db_table = "users_user_groups"
        constraints = [
            models.UniqueConstraint(fields=('user', 'role', 'site'),
                                    name='unique_user_role_site'),
        ]
        verbose_name = _("Access Group")
        verbose_name_plural = _("Access Groups")

    @property
    def _key(self):
        """
        Convenience function to make eq overrides easier and clearer.
        Arbitrary decision that group is primary, followed by site and then user
        """
        return self.role, self.site, self.user_id

    def __eq__(self, other):
        """
        Overriding eq b/c the django impl relies on the primary key which
        requires fetch. Sometimes we just want to compare groups w/o doing
        another fetch.
        """
        # noinspection PyProtectedMember
        return type(self) == type(other) and self._key == other._key

    def __hash__(self):
        return hash(self._key)

    def __str__(self):
        return "[AccessGroup] user: {}  role: {}  site: {}".format(
            self.user_id, self.role, self.site)


class StudentProfile(models.Model):
    enrollment_year = models.PositiveSmallIntegerField(
        _("CSCUser|enrollment year"),
        validators=[MinValueValidator(1990)],
        blank=True,
        null=True)
    # FIXME: remove
    graduation_year = models.PositiveSmallIntegerField(
        _("CSCUser|graduation year"),
        blank=True,
        validators=[MinValueValidator(1990)],
        null=True)
    curriculum_year = models.PositiveSmallIntegerField(
        _("CSCUser|Curriculum year"),
        validators=[MinValueValidator(2000)],
        blank=True,
        null=True)
    branch = models.ForeignKey(
        "learning.Branch",
        verbose_name=_("Branch"),
        related_name="+",  # Disable backwards relation
        on_delete=models.SET_NULL,
        null=True,
        blank=True)
    university = models.CharField(
        _("University"),
        max_length=255,
        blank=True)
    phone = models.CharField(
        _("Phone"),
        max_length=40,
        blank=True)
    uni_year_at_enrollment = models.CharField(
        _("StudentInfo|University year"),
        choices=AcademicDegreeYears.choices,
        max_length=2,
        help_text=_("at enrollment"),
        null=True,
        blank=True)
    # FIXME: remove
    areas_of_study = models.ManyToManyField(
        'study_programs.AcademicDiscipline',
        verbose_name=_("StudentInfo|Areas of study"),
        blank=True)

    class Meta:
        abstract = True


class User(LearningPermissionsMixin, StudentProfile, UserThumbnailMixin,
           AbstractBaseUser):
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']
    ENROLLMENT_CACHE_KEY = "_student_enrollment_{}"
    GENDER_MALE = GenderTypes.MALE
    GENDER_FEMALE = GenderTypes.FEMALE

    username_validator = UnicodeUsernameValidator()

    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        validators=[username_validator],
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    email = models.EmailField(_('email address'), unique=True)
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    is_superuser = models.BooleanField(
        _('superuser status'),
        default=False,
        help_text=_(
            'Designates that this user has all permissions without '
            'explicitly assigning them.'
        ),
    )
    gender = models.CharField(_("Gender"), max_length=1,
                              choices=GenderTypes.choices)
    modified = AutoLastModifiedField(_('modified'))
    patronymic = models.CharField(
        _("CSCUser|patronymic"),
        max_length=100,
        blank=True)
    photo = ImageField(
        _("CSCUser|photo"),
        upload_to="photos/",
        blank=True)
    cropbox_data = JSONField(
        blank=True,
        null=True
    )
    bio = models.TextField(
        _("CSCUser|note"),
        help_text=_("LaTeX+Markdown is enabled"),
        blank=True)
    city = models.ForeignKey(City, verbose_name=_("Default city"),
                             help_text=_("CSCUser|city"),
                             blank=True, null=True,
                             on_delete=models.SET_NULL)
    # FIXME: why not null? The same for github_id
    yandex_id = models.CharField(
        _("Yandex ID"),
        max_length=80,
        validators=[RegexValidator(regex="^[^@]*$",
                                   message=_("Only the part before "
                                             "\"@yandex.ru\" is expected"))],
        blank=True)
    github_id = models.CharField(
        _("Github ID"),
        max_length=80,
        validators=[GITHUB_LOGIN_VALIDATOR],
        blank=True)
    stepic_id = models.PositiveIntegerField(
        _("stepik.org ID"),
        blank=True,
        null=True)
    private_contacts = models.TextField(
        _("Contact information"),
        help_text=("{}; {}"
                   .format(_("LaTeX+Markdown is enabled"),
                           _("will be shown only to logged-in users"))),
        blank=True)
    status = models.CharField(
        choices=StudentStatuses.choices,
        verbose_name=_("Status"),
        help_text=_("Status|HelpText"),
        max_length=15,
        blank=True)
    status_last_change = MonitorStatusField(
        UserStatusLog,
        verbose_name=_("Status changed"),
        blank=True,
        null=True,
        editable=False,
        monitored='status',
        logging_model=UserStatusLog,
        on_delete=models.CASCADE)
    comment = models.TextField(
        _("Comment"),
        help_text=LATEX_MARKDOWN_ENABLED,
        blank=True)
    comment_changed_at = MonitorField(
        monitor='comment',
        verbose_name=_("Comment changed"))
    comment_last_author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Author of last edit"),
        on_delete=models.PROTECT,
        related_name='user_commented',
        blank=True,
        null=True)
    workplace = models.CharField(
        _("Workplace"),
        max_length=200,
        blank=True)
    index_redirect = models.CharField(
        _("Index Redirect Option"),
        max_length=200,
        choices=PublicRoute.choices(),
        blank=True)

    objects = CustomUserManager()

    class Meta:
        db_table = 'users_user'
        verbose_name = _("CSCUser|user")
        verbose_name_plural = _("CSCUser|users")

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def get_group_permissions(self, obj=None):
        return PermissionsMixin.get_group_permissions(self, obj)

    def get_all_permissions(self, obj=None):
        return PermissionsMixin.get_all_permissions(self, obj)

    def has_perm(self, perm, obj=None):
        # Active superusers have all permissions implicitly added
        # by Django but no more
        is_registered_permission = perm not in all_permissions
        if self.is_active and self.is_superuser and is_registered_permission:
            return True
        # Otherwise we need to check the backends.
        return _user_has_perm(self, perm, obj)

    def has_perms(self, perm_list, obj=None):
        return PermissionsMixin.has_perms(self, perm_list, obj)

    def has_module_perms(self, app_label):
        return PermissionsMixin.has_module_perms(self, app_label)

    def save(self, **kwargs):
        created = self.pk is None
        password_changed = self._password is not None
        if self.email and not self.yandex_id:
            username, domain = self.email.split("@", 1)
            if domain in YANDEX_DOMAINS:
                self.yandex_id = username
        super().save(**kwargs)
        # Schedules redis queue task to update user password in gerrit's
        # LDAP database if password was changed.
        gerrit_sync_enabled = getattr(settings, "LDAP_SYNC_PASSWORD", False)
        if not created and password_changed and gerrit_sync_enabled:
            if self.roles.intersection(GROUPS_IMPORT_TO_GERRIT):
                update_password_in_gerrit.delay(user_id=self.pk)
        elif created and gerrit_sync_enabled:
            # TODO: schedule task for creating LDAP account
            pass

    def add_group(self, role, site_id: int = None):
        """Add new role associated with the current site by default"""
        site_id = site_id or settings.SITE_ID
        self.groups.get_or_create(user=self, role=role, site_id=site_id)

    def remove_group(self, role, site_id: int = None):
        sid = site_id or settings.SITE_ID
        self.groups.filter(user=self, role=role, site_id=sid).delete()

    @property
    def city_code(self):
        city_code = getattr(self, "city_id", None)
        return city_code if city_code else None

    @property
    def is_expelled(self):
        return self.status == StudentStatuses.EXPELLED

    @staticmethod
    def create_student_from_applicant(applicant):
        """
        Create new model or override existent with data from applicant form.
        """
        from admission.models import Applicant
        try:
            user = User.objects.get(email=applicant.email)
        except User.DoesNotExist:
            username = applicant.email.split("@", maxsplit=1)[0]
            if User.objects.filter(username=username).exists():
                username = User.generate_random_username(attempts=5)
            if not username:
                raise RuntimeError(
                    "Всё плохо. Имя {} уже занято. Cлучайное имя сгенерировать "
                    "не удалось".format(username))
            random_password = User.objects.make_random_password()
            user = User.objects.create_user(username=username,
                                            email=applicant.email,
                                            password=random_password)
        if applicant.status == Applicant.VOLUNTEER:
            user.add_group(Roles.VOLUNTEER)
        else:
            user.add_group(Roles.STUDENT)
        user.add_group(Roles.STUDENT, site_id=settings.CLUB_SITE_ID)
        # Migrate data from application form to user profile
        same_attrs = [
            "first_name",
            "patronymic",
            "stepic_id",
            "phone"
        ]
        for attr_name in same_attrs:
            setattr(user, attr_name, getattr(applicant, attr_name))
        user.last_name = applicant.surname
        user.enrollment_year = user.curriculum_year = timezone.now().year
        # Looks like the same fields below
        user.yandex_id = applicant.yandex_id if applicant.yandex_id else ""
        # For github store part after github.com/
        if applicant.github_id:
            user.github_id = applicant.github_id.split("github.com/",
                                                       maxsplit=1)[-1]
        user.workplace = applicant.workplace if applicant.workplace else ""
        user.uni_year_at_enrollment = applicant.course
        user.city_id = applicant.campaign.city_id
        user.university = applicant.university.name
        user.save()
        return user

    @staticmethod
    def generate_random_username(length=30,
                                 chars=ascii_lowercase + digits,
                                 split=4,
                                 delimiter='-',
                                 attempts=10):
        if not attempts:
            return None

        username = ''.join([choice(chars) for _ in range(length)])

        if split:
            username = delimiter.join(
                [username[start:start + split] for start in
                 range(0, len(username), split)])

        try:
            User.objects.get(username=username)
            return User.generate_random_username(
                length=length, chars=chars, split=split, delimiter=delimiter,
                attempts=attempts - 1)
        except User.DoesNotExist:
            return username

    @property
    def password_hash_ldap(self) -> Optional[bytes]:
        """
        Converts Django's password hash representation to LDAP compatible
        hasher format. Supports pbkdf2 hasher only.
        """
        algorithm, iterations, salt, hash = self.password.split('$', 3)
        if algorithm == "pbkdf2_sha256":
            ldap_hasher_code = "{PBKDF2-SHA256}"
        elif algorithm == "pbkdf2_sha512":
            ldap_hasher_code = "{PBKDF2-SHA512}"
        elif algorithm == "pbkdf2_sha1":
            ldap_hasher_code = "{PBKDF2-SHA1}"
        else:
            return None
        # Works like `passlib.utils.binary.ab64_encode` except
        # converting "+" to "."
        ab64_salt = base64.b64encode(salt.encode("utf-8")).rstrip(b"=\n")
        h = f"{ldap_hasher_code}{iterations}${ab64_salt.decode('utf-8')}${hash}"
        return h.encode("utf-8")

    @property
    def ldap_username(self):
        """
        Portable Filename Character Set (according to POSIX.1-2017) is used for
        username since @ in username can be misleading when you connected
        over ssh. `foo@localhost.ru@domain.ltd` really looks weird.
        """
        return self.email.replace("@", ".")

    def __str__(self):
        return smart_text(self.get_full_name(True))

    def get_absolute_url(self, subdomain=None):
        return reverse('user_detail', args=[self.pk], subdomain=subdomain)

    def get_student_profile_url(self, subdomain=None):
        return reverse('student_profile', args=[self.pk], subdomain=subdomain)

    def get_update_profile_url(self):
        return reverse('user_update', args=[self.pk])

    def get_classes_icalendar_url(self):
        # Returns relative path
        return reverse('user_ical_classes', args=[self.pk])

    def get_assignments_icalendar_url(self):
        return reverse('user_ical_assignments', args=[self.pk])

    def teacher_profile_url(self):
        return reverse('teacher_detail', args=[self.pk])

    def get_applicant_form_url(self):
        try:
            applicant_form_url = reverse("admission:applicant_detail",
                                         args=[self.applicant.pk])
        except ObjectDoesNotExist:
            applicant_form_url = None
        return applicant_form_url

    def get_full_name(self, last_name_first=False):
        """
        Returns first name, last name and patronymic, with a space in between
        or username if not enough data.

        For bibliographic list use `last_name_first=True`
        """
        if last_name_first:
            parts = (self.last_name, self.first_name, self.patronymic)
        else:
            parts = (self.first_name, self.patronymic, self.last_name)
        full_name = smart_text(" ".join(p for p in parts if p).strip())
        return full_name or self.username

    def get_short_name(self):
        return (smart_text(" ".join([self.first_name, self.last_name]).strip())
                or self.username)

    def get_abbreviated_name(self):
        parts = [self.first_name[:1], self.patronymic[:1], self.last_name]
        abbrev_name = smart_text(". ".join(p for p in parts if p).strip())
        return abbrev_name or self.username

    def get_abbreviated_short_name(self, last_name_first=True):
        first_letter = self.first_name[:1] + "." if self.first_name else ""
        if last_name_first:
            parts = [self.last_name, first_letter]
        else:
            parts = [first_letter, self.last_name]
        return " ".join(parts).strip() or self.username

    def get_abbreviated_name_in_latin(self):
        """
        Returns transliterated user surname + rest initials in lower case.
        Fallback to username. Useful for LDAP accounts.

        Жуков Иван Викторович -> zhukov.i.v
        Иванов Кирилл -> ivanov.k
        """
        parts = [self.last_name, self.first_name[:1], self.patronymic[:1]]
        parts = [p.lower() for p in parts if p] or [self.username.lower()]
        # TODO: remove apostrophe
        return ".".join(parts).translate(ru_en_mapping)

    @property
    def photo_data(self):
        if self.photo:
            try:
                return {
                    "url": self.photo.url,
                    "width": self.photo.width,
                    "height": self.photo.height,
                    "cropbox": self.cropbox_data
                }
            except (IOError, OSError):
                pass
        return None

    def get_short_bio(self):
        """Returns only the first paragraph from the bio."""
        normalized_bio = normalize_newlines(self.bio)
        lf = normalized_bio.find("\n")
        return self.bio if lf == -1 else normalized_bio[:lf]

    @cached_property
    def _cached_groups(self) -> set:
        # FIXME: restrict by sett
        try:
            gs = self._prefetched_objects_cache['groups']
            roles = set(g.role for g in gs if g.site_id == settings.SITE_ID)
        except (AttributeError, KeyError):
            roles = set(self.groups
                        .filter(site_id=settings.SITE_ID)
                        .values_list("role", flat=True))
        return roles

    @cached_property
    def roles(self) -> set:
        return self._cached_groups

    def get_enrollment(self, course_id: int) -> Optional["Enrollment"]:
        """
        Query enrollment from db on first call and cache the result. Cache
        won't be refreshed if enrollment was deleted or changed after call.
        """
        from learning.models import Enrollment
        if self.is_student or self.is_volunteer or self.is_graduate:
            cache_key = self.ENROLLMENT_CACHE_KEY.format(course_id)
            if not hasattr(self, cache_key):
                e = (Enrollment.active
                     .filter(student=self,
                             course_id=course_id)
                     .order_by()
                     .first())
                setattr(self, cache_key, e)
            return getattr(self, cache_key)
        return None

    # TODO: move to Project manager?
    def get_projects_queryset(self):
        """Returns projects through ProjectStudent intermediate model"""
        if is_club_site():
            return None
        return (self.projectstudent_set
                .select_related('project', 'project__semester')
                .order_by('project__semester__index'))

    def get_redirect_options(self):
        """
        Returns list of website sections available for redirect to current
        authenticated user
        """
        sections = []
        if self.is_project_reviewer or self.is_curator_of_projects:
            sections.append(PublicRoute.PROJECTS.choice)
        if self.is_interviewer:
            sections.append(PublicRoute.ADMISSION.choice)
        if self.is_student or self.is_volunteer:
            sections.append(PublicRoute.LEARNING.choice)
        if self.is_teacher:
            sections.append(PublicRoute.TEACHING.choice)
        if self.is_curator:
            sections.append(PublicRoute.STAFF.choice)
        return sections

    def stats(self, current_term):
        """
        Stats for SUCCESSFULLY completed courses and enrollments in 
        requested term.
        Additional DB queries may occur:
            * enrollment_set
            * enrollment_set__course (for each enrollment)
            * enrollment_set__course__courseclasses (for each course)
            * onlinecourserecord_set
            * shadcourserecord_set
        """
        center_courses = set()
        club_courses = set()
        club_adjusted = 0
        failed_total = 0
        in_current_term_total = 0  # center, club and shad courses
        in_current_term_courses = set()  # center and club courses
        in_current_term_passed = 0  # Center and club courses
        in_current_term_failed = 0  # Center and club courses
        in_current_term_in_progress = 0  # Center and club courses
        # FIXME: add test for `is_deleted=False`. Check all incomings for `enrollment_set`
        for e in self.enrollment_set.filter(is_deleted=False).all():
            in_current_term = e.course.semester_id == current_term.pk
            if in_current_term:
                in_current_term_total += 1
                in_current_term_courses.add(e.course.meta_course_id)
            if e.course.is_open:
                # FIXME: Something wrong with this approach.
                # FIXME: Look for `classes_total` annotation and fix
                if hasattr(e, "classes_total"):
                    classes_total = e.classes_total
                else:
                    classes_total = (e.course.courseclass_set.count())
                contribution = 0.5 if classes_total < 6 else 1
                if e.grade in GradeTypes.satisfactory_grades:
                    club_courses.add(e.course.meta_course_id)
                    club_adjusted += contribution
                    in_current_term_passed += int(in_current_term)
                elif in_current_term:
                    if is_negative_grade(e.grade):
                        failed_total += 1
                        in_current_term_failed += 1
                    else:
                        in_current_term_in_progress += contribution
                else:
                    failed_total += 1
            else:
                if e.grade in GradeTypes.satisfactory_grades:
                    center_courses.add(e.course.meta_course_id)
                    in_current_term_passed += int(in_current_term)
                elif in_current_term:
                    if is_negative_grade(e.grade):
                        failed_total += 1
                        in_current_term_failed += 1
                    else:
                        in_current_term_in_progress += 1
                else:
                    failed_total += 1
        online_total = len(self.onlinecourserecord_set.all())
        shad_total = 0
        for c in self.shadcourserecord_set.all():
            if c.grade in GradeTypes.satisfactory_grades:
                shad_total += 1
            if c.semester_id == current_term.pk:
                in_current_term_total += 1
                if is_negative_grade(c.grade):
                    failed_total += 1
            # `not graded` == failed for passed terms
            elif c.grade not in GradeTypes.satisfactory_grades:
                failed_total += 1

        return {
            "failed": {"total": failed_total},
            # All the time
            "passed": {
                "total": len(center_courses) + online_total + shad_total +
                         len(club_courses),
                "adjusted": len(center_courses) + online_total + shad_total +
                            club_adjusted,
                "center_courses": center_courses,
                "club_courses": club_courses,
                "online_total": online_total,
                "shad_total": shad_total
            },
            "in_term": {
                "total": in_current_term_total,
                "courses": in_current_term_courses,  # center and club courses
                "passed": in_current_term_passed,  # center and club
                "failed": in_current_term_failed,  # center and club
                # FIXME: adusted value, not int
                "in_progress": in_current_term_in_progress,
            }
        }


class OnlineCourseRecord(TimeStampedModel):
    student = models.ForeignKey(
        User,
        verbose_name=_("Student"),
        on_delete=models.CASCADE)
    name = models.CharField(_("Course|name"), max_length=255)

    class Meta:
        ordering = ["name"]
        verbose_name = _("Online course record")
        verbose_name_plural = _("Online course records")

    def __str__(self):
        return smart_text(self.name)


class SHADCourseRecord(TimeStampedModel):
    student = models.ForeignKey(
        User,
        verbose_name=_("Student"),
        on_delete=models.CASCADE)
    name = models.CharField(_("Course|name"), max_length=255)
    teachers = models.CharField(_("Teachers"), max_length=255)
    semester = models.ForeignKey(
        'courses.Semester',
        verbose_name=_("Semester"),
        on_delete=models.PROTECT)

    grade = models.CharField(
        max_length=100,
        verbose_name=_("Enrollment|grade"),
        choices=SHADCourseGradeTypes.choices,
        default=SHADCourseGradeTypes.NOT_GRADED)

    class Meta:
        ordering = ["name"]
        verbose_name = _("SHAD course record")
        verbose_name_plural = _("SHAD course records")

    @property
    def grade_display(self):
        return SHADCourseGradeTypes.values[self.grade]

    def __str__(self):
        return smart_text("{} [{}]".format(self.name, self.student_id))


class EnrollmentCertificate(TimeStampedModel):
    signature = models.CharField(_("Reference|signature"), max_length=255)
    note = models.TextField(_("Reference|note"), blank=True)

    student = models.ForeignKey(
        User,
        verbose_name=_("Student"),
        on_delete=models.CASCADE,
        related_name="enrollment_certificates")

    class Meta:
        ordering = ["signature"]
        verbose_name = _("Student Reference")
        verbose_name_plural = _("Student References")

    def __str__(self):
        return smart_text(self.student)

    def get_absolute_url(self):
        return reverse('user_reference_detail', args=[self.student_id, self.pk])
