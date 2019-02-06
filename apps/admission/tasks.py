import logging

from django.apps import apps
from django.db.models import Q
from django.utils import translation, timezone
from django.utils.timezone import now
from django_rq import job
from post_office import mail

from api.providers.yandex_contest import YandexContestAPIException, YandexContestAPI, \
    RegisterStatus
from admission.models import Test, Contest

logger = logging.getLogger(__name__)


def notify_admin_bad_token(campaign_id):
    """Send message about bad auth token for Yandex.Contest API"""
    pass


@job('high')
def register_in_yandex_contest(applicant_id, language_code):
    """Register user in Yandex.Contest, then send email with summary"""
    translation.activate(language_code)
    Applicant = apps.get_model('admission', 'Applicant')
    Test = apps.get_model('admission', 'Test')
    applicant = (Applicant.objects
                 .filter(pk=applicant_id)
                 .select_related("campaign", "online_test", "campaign__city")
                 .first())
    campaign = applicant.campaign
    if not applicant.yandex_id:
        logger.error(f"Empty yandex login for applicant id = {applicant_id}")
        raise AttributeError("Empty yandex id")
    contest_id = applicant.online_test.yandex_contest_id
    if not contest_id:  # Can't imagine use case when it's possible
        logger.error(f"No contest assigned to applicant id = {applicant_id}")
        raise AttributeError("Empty contest id")
    api = YandexContestAPI(access_token=campaign.access_token,
                           refresh_token=campaign.refresh_token)
    try:
        status_code, data = api.register_in_contest(applicant.yandex_id,
                                                    contest_id)
    except YandexContestAPIException as e:
        error_status_code, text = e.args
        if error_status_code == RegisterStatus.BAD_TOKEN:
            notify_admin_bad_token(campaign.pk)
        logger.error(f"Yandex.Contest api request error [id = {applicant_id}]")
        raise

    # Update testing status and generate notification
    update_fields = {
        "status": Test.REGISTERED,
        "contest_status_code": status_code,
    }
    if status_code == RegisterStatus.CREATED:
        participant_id = data
        update_fields["contest_participant_id"] = participant_id
    else:  # 409 - already registered for this contest
        registered = (Test.objects
                      .filter(
                        yandex_contest_id=contest_id,
                        contest_status_code=RegisterStatus.CREATED,
                        applicant__campaign__current=True,
                        applicant__yandex_id=applicant.yandex_id)
                      .only("contest_participant_id")
                      .first())
        # 1. Admins/judges could be registered directly through contest admin,
        # so we haven't info about there participant id and can't easily get
        # there results later, but still allow them testing application form
        # 2. When registering user in contest on `read timeout` response
        # we lost information about there participant id without any ability to
        # restore it through API (until the participant appears in
        # results table)
        if registered:
            participant_id = registered.contest_participant_id
            update_fields["contest_participant_id"] = participant_id
    (Test.objects
     .filter(applicant_id=applicant_id)
     .update(**update_fields))

    mail.send(
        [applicant.email],
        sender='CS центр <info@compscicenter.ru>',
        template=campaign.template_name,
        context={
            'FIRST_NAME': applicant.first_name,
            'SURNAME': applicant.surname,
            'PATRONYMIC': applicant.patronymic,
            'EMAIL': applicant.email,
            'CITY': applicant.campaign.city.name,
            'PHONE': applicant.phone,
            'CONTEST_ID': contest_id,
            'YANDEX_LOGIN': applicant.yandex_id,
        },
        render_on_delivery=True,
        backend='ses',
    )


# FIXME: надо отлавливать все timeout'ы при запросе, т.к. в этом случае поле processed_at не будет обновлено и будет попадать в очередь задач на исполнение
# TODO: What if rq.timeouts.JobTimeoutException?
@job('default')
def import_testing_results(task_id=None):
    Applicant = apps.get_model('admission', 'Applicant')
    Campaign = apps.get_model('admission', 'Campaign')
    Task = apps.get_model('tasks', 'Task')
    if task_id:
        try:
            task = Task.objects.unlocked(timezone.now()).get(pk=task_id)
        except Task.DoesNotExist:
            logger.error(f"Task with id = {task_id} doesn't exist.")
            return
    task.lock(locked_by="rqworker")
    current_campaigns = Campaign.objects.filter(current=True)
    if not current_campaigns:
        # TODO: mark task as failed
        return
    now = timezone.now()
    # Campaigns are the same now, but handle them separately,
    # since this behavior can be changed in the future.
    for campaign in current_campaigns:
        # TODO: add contest deadline and check that contest has ended
        api = YandexContestAPI(access_token=campaign.access_token)
        for contest in campaign.contests.filter(type=Contest.TYPE_TEST).all():
            contest_id = contest.contest_id
            paging = {
                "page_size": 50,
                "page": 1
            }
            logger.debug(f"Starting processing contest {contest_id}")
            # Note, that scoreboard can be modified at any moment.
            # It means we can miss some results during the parsing
            # if someone has improved his position and moved to scoreboard
            # `page` which we are already processed.
            scoreboard_total = 0
            updated_total = 0
            while True:
                try:
                    status, json_data = api.standings(contest_id, **paging)
                    # Assignment titles
                    if "titles" not in contest.details:
                        if not contest.details:
                            contest.details = {}
                        titles = [t["name"] for t in json_data["titles"]]
                        contest.details["titles"] = titles
                        contest.save()
                    page_total = 0
                    for row in json_data['rows']:
                        scoreboard_total += 1
                        page_total += 1
                        yandex_login = row['participantInfo']['login']
                        participant_id = row['participantInfo']['id']
                        score_str: str = row['score']
                        score_str = score_str.replace(',', '.')
                        score = int(round(float(score_str)))
                        # TODO: Обновлять статус? Но это +1 запрос на каждый результат, если делать это точно
                        participant = (Q(applicant__yandex_id=yandex_login) |
                                       Q(contest_participant_id=participant_id))
                        # Participant progress
                        scores = [a["score"] for a in row["problemResults"]]
                        update_fields = {
                            "score": score,
                            "details": {"scores": scores}
                        }
                        updated = (Test.objects
                                   .filter(applicant__campaign_id=campaign.pk,
                                           yandex_contest_id=contest_id,
                                           status=Test.REGISTERED)
                                   .filter(participant)
                                   .update(**update_fields))
                        updated_total += updated
                    if page_total < paging["page_size"]:
                        break
                    paging["page"] += 1
                    # TODO: handle read timeout?
                except YandexContestAPIException as e:
                    error_status_code, text = e.args
                    if error_status_code == RegisterStatus.BAD_TOKEN:
                        notify_admin_bad_token(campaign.pk)
                    logger.exception(f"Yandex.Contest API error. "
                                     f"Method: `standings` "
                                     f"Contest: {contest_id}")
                    break
            logger.debug(f"Total participants {scoreboard_total}")
            logger.debug(f"Updated {updated_total}")
        # FIXME: если контест закончился - для всех, кого нет в scoreboard надо проставить соответствующий статус анкете и тесту.
    task.processed_at = timezone.now()
    task.save()