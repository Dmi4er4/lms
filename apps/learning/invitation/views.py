
from django.conf import settings
from django.contrib import messages
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponseRedirect, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from registration.backends.default.views import RegistrationView, ActivationView
from vanilla import TemplateView, GenericView

from auth.tasks import send_activation_email, ActivationEmailContext
from auth.views import LoginView
from core.exceptions import Redirect
from core.urls import reverse
from courses.views.mixins import CourseURLParamsMixin
from learning.invitation.forms import InvitationLoginForm, \
    InvitationRegistrationForm
from learning.models import Invitation, EnrollmentInvitation
from learning.roles import Roles
from learning.services import EnrollmentService, AlreadyEnrolled, \
    CourseCapacityFull


class InvitationParamMixin:
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        qs = (Invitation.objects
              .filter(token=kwargs['token']))
        self.invitation = get_object_or_404(qs)
        if not self.invitation.is_active:
            raise Http404


class InvitationView(InvitationParamMixin, TemplateView):
    template_name = "learning/invitation/invitation_courses.html"

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = reverse("invitation:login",
                                kwargs={"token": self.invitation.token},
                                subdomain=settings.LMS_SUBDOMAIN)
            return HttpResponseRedirect(redirect_to=login_url)
        context = self.get_context_data()
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        course_invitations = (self.invitation.courses.through.objects
                              .select_related('course',
                                              'course__meta_course',
                                              'course__semester'))
        # TODO: Count how many active inviattions.
        return {
            'invitations': course_invitations,
        }


class InvitationLoginView(InvitationParamMixin, LoginView):
    form_class = InvitationLoginForm
    template_name = "learning/invitation/auth.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            url = self.invitation.get_absolute_url()
            return HttpResponseRedirect(redirect_to=url)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        register_url = reverse("invitation:registration",
                               kwargs={"token": self.invitation.token},
                               subdomain=settings.LMS_SUBDOMAIN)
        context["register_url"] = register_url
        return context

    def form_valid(self, form):
        # TODO: добавить группу Invited (если нет других? А как это определить)
        # TODO: накинуть отделение из приглашения, если не установлен city_id
        # TODO: всё-таки логировать входы из этой формы и при регистрации по определенному инвайту?
        return super().form_valid(form)

    def get_success_url(self):
        return self.invitation.get_absolute_url()


class InvitationRegisterView(InvitationParamMixin, RegistrationView):
    form_class = InvitationRegistrationForm
    SEND_ACTIVATION_EMAIL = False  # Prevent sending email on request
    template_name = "learning/invitation/registration.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            url = self.invitation.get_absolute_url()
            return HttpResponseRedirect(redirect_to=url)
        context = self.get_context_data()
        return self.render_to_response(context)

    def register(self, form):
        new_user = super().register(form)
        new_user.add_group(Roles.INVITED)
        site = get_current_site(self.request)
        activation_url = reverse("invitation:activate", kwargs={
            "token": self.invitation.token,
            "activation_key": new_user.registrationprofile.activation_key
        }, subdomain=settings.LMS_SUBDOMAIN)
        context = ActivationEmailContext(
            site_name=site.name,
            activation_url=activation_url,
            language_code=self.request.LANGUAGE_CODE)
        send_activation_email.delay(context, new_user.registrationprofile.pk)
        return new_user

    def registration_allowed(self):
        return True

    def get_success_url(self, user=None):
        return reverse("invitation:registration_complete",
                       subdomain=settings.LMS_SUBDOMAIN)


class InvitationRegisterCompleteView(TemplateView):
    template_name = 'learning/invitation/registration_complete.html'


class InvitationActivationCompleteView(TemplateView):
    template_name = 'learning/invitation/activation_complete.html'


class InvitationActivationView(InvitationParamMixin, ActivationView):
    template_name = 'learning/invitation/activation_fail.html'

    def get_success_url(self, user):
        messages.success(self.request, _("Учетная запись активирована."),
                         extra_tags='timeout')
        return self.invitation.get_absolute_url()


class CourseInvitationEnrollView(CourseURLParamsMixin, GenericView):
    def post(self, request, *args, **kwargs):
        user = request.user
        qs = (EnrollmentInvitation.objects
              .select_related('invitation')
              .filter(token=kwargs['course_token'], course=self.course))
        course_invitation = get_object_or_404(qs)
        invitation = course_invitation.invitation
        if not user.has_perm("learning.enroll_in_course_by_invitation",
                             course_invitation):
            if self.course.is_capacity_limited and not self.course.places_left:
                msg = _("No places available, sorry")
                messages.error(request, msg, extra_tags='timeout')
                raise Redirect(to=invitation.get_absolute_url())
            return HttpResponseForbidden()
        try:
            EnrollmentService.enroll(user, self.course, reason_entry='')
            msg = _("You are successfully enrolled in the course")
            messages.success(self.request, msg, extra_tags='timeout')
            redirect_to = self.course.get_absolute_url()
        except AlreadyEnrolled:
            msg = _("You are already enrolled in the course")
            messages.warning(request, msg, extra_tags='timeout')
            redirect_to = self.course.get_absolute_url()
        except CourseCapacityFull:
            msg = _("No places available, sorry")
            messages.error(request, msg, extra_tags='timeout')
            redirect_to = invitation.get_absolute_url()
        raise Redirect(to=redirect_to)