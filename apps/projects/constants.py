from django.utils.translation import ugettext_lazy as _
from djchoices import DjangoChoices, C

REPORTING_NOTIFY_BEFORE_START = 3  # days
REPORTING_NOTIFY_BEFORE_DEADLINE = 1  # days


class ProjectTypes(DjangoChoices):
    practice = C('practice', _("StudentProject|Practice"))
    research = C('research', _("StudentProject|Research"))