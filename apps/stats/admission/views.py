import datetime

from django.db.models import Count, When, IntegerField, Case, Q, Func, F
from django.db.models.functions import TruncDate, ExtractMonth, ExtractDay, \
    ExtractYear
from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_pandas import PandasView
from rest_pandas.serializers import SimpleSerializer, PandasSerializer

from api.permissions import CuratorAccessPermission
from admission.models import Applicant, Test, Exam, Campaign
from core.timezone import now_local
from stats.admission.pandas_serializers import \
    CampaignResultsTimelineSerializer, \
    ScoreByUniversitiesSerializer, ScoreByCoursesSerializer, \
    CampaignResultsByUniversitiesSerializer, \
    CampaignResultsByCoursesSerializer, ApplicationSubmissionPandasSerializer
from stats.admission.serializers import StageByYearSerializer, \
    ApplicationSubmissionSerializer
from stats.renderers import ListRenderersMixin

TestingCountAnnotation = Count(
    Case(When(Q(online_test__isnull=False, online_test__score__isnull=False), then=1),
         output_field=IntegerField()))
ExaminationCountAnnotation = Count(Case(When(exam__isnull=False, then=1),
                                        output_field=IntegerField()))
InterviewingCountAnnotation = Count(Case(When(interview__isnull=False, then=1),
                                         output_field=IntegerField()))

STATUSES = [Applicant.ACCEPT,
            Applicant.ACCEPT_IF,
            Applicant.REJECTED_BY_INTERVIEW,
            Applicant.VOLUNTEER,
            Applicant.THEY_REFUSED]


class CampaignsStagesByYears(ReadOnlyModelViewSet):
    """Admission stages by years for provided city."""
    permission_classes = [CuratorAccessPermission]

    def list(self, request, *args, **kwargs):
        city_code = self.kwargs.get('city_code')
        applicants = (Applicant.objects
                      .filter(campaign__city_id=city_code)
                      .values('campaign_id', 'campaign__year')
                      .annotate(application_form=Count("campaign_id"),
                                testing=TestingCountAnnotation,
                                examination=ExaminationCountAnnotation,
                                interviewing=InterviewingCountAnnotation)
                      # Under the assumption that campaign year is unique
                      .order_by('campaign__year'))
        return Response(applicants)


class CampaignStagesByUniversities(ReadOnlyModelViewSet):
    """Admission campaign stages by universities."""
    permission_classes = [CuratorAccessPermission]
    serializer_class = SimpleSerializer

    def get_queryset(self):
        campaign_id = self.kwargs.get('campaign_id')
        return (Applicant.objects
                .filter(campaign_id=campaign_id)
                .values('university_id', 'university__name')
                .annotate(application_form=Count("campaign_id"),
                          testing=TestingCountAnnotation,
                          examination=ExaminationCountAnnotation,
                          interviewing=InterviewingCountAnnotation))


class CampaignStagesByCourses(ReadOnlyModelViewSet):
    """Admission campaign stages by courses."""
    permission_classes = [CuratorAccessPermission]
    serializer_class = StageByYearSerializer

    def get_queryset(self):
        campaign_id = self.kwargs.get('campaign_id')
        return (Applicant.objects
                .filter(campaign_id=campaign_id)
                .values('course')
                .annotate(application_form=Count("campaign_id"),
                          testing=TestingCountAnnotation,
                          examination=ExaminationCountAnnotation,
                          interviewing=InterviewingCountAnnotation)
                .order_by("course"))


class ApplicationFormSubmissionByDays(ListAPIView):
    permission_classes = [CuratorAccessPermission]
    serializer_class = SimpleSerializer

    def list(self, request, *args, **kwargs):
        campaigns = (Campaign.objects
                     .filter(city_id=self.kwargs['city_code'], year__gte=2017))
        data = self.get_stat(campaigns)
        return Response(data)

    @staticmethod
    def get_filters(campaigns):
        dates = Q()
        campaign_ids = []
        for c in campaigns:
            application_period = Q(created__gte=c.application_starts_at,
                                   created__lte=c.application_ends_at)
            dates |= application_period
            campaign_ids.append(c.id)
        return Q(campaign__in=campaign_ids) & dates

    def get_stat(self, campaigns):
        filters = self.get_filters(campaigns)
        qs = (Applicant.objects
              .filter(filters)
              .annotate(month=ExtractMonth('created'),
                        day=ExtractDay('created'),
                        year=ExtractYear('created'))
              .values_list('year', 'month', 'day')
              .annotate(total=Count("id"))
              .order_by('year', 'month', 'day'))
        # XXX: Aggregated data doesn't include days without applications.
        data = {}
        application_start = {}
        for c in campaigns:
            start = c.application_starts_at_local().date()
            end = c.application_ends_at_local().date()
            data[c.year] = [0 for _ in range((end - start).days + 1)]
            application_start[c.year] = start
        for year, month, day, total in qs:
            created = datetime.date(year=year, month=month, day=day)
            index = (created - application_start[year]).days
            # Applications could be sent before official release
            if index >= 0:
                data[year][index] = total
        active_campaign = next((c for c in campaigns if c.current), None)
        for year in data:
            xs = data[year]
            index = len(xs)
            # For current campaign calculate partial sums until today
            if active_campaign and active_campaign.year == year:
                start = active_campaign.application_starts_at_local().date()
                today = now_local(active_campaign.get_city_timezone()).date()
                index = min(index, (today - start).days + 1)
            # Partial sums
            for i in range(1, index):
                xs[i] += xs[i - 1]
        return data


class CampaignStatsApplicantsResults(ListRenderersMixin, PandasView):
    """
    Admission campaign results by applicants.

    Not sure how many statuses will be needed in the future, so combine them
    on application lvl instead of aggregation on DB.
    """
    permission_classes = [CuratorAccessPermission]
    serializer_class = SimpleSerializer
    pandas_serializer_class = CampaignResultsTimelineSerializer

    def get_queryset(self):
        city_code = self.kwargs.get('city_code')
        qs = (Applicant.objects
              .filter(campaign__city_id=city_code,
                      status__in=STATUSES)
              .values('campaign__year', 'status')
              .annotate(total=Count("status"))
              # Under the assumption that campaign year is unique.
              .order_by('campaign__year'))
        return qs


class CampaignResultsByUniversities(ListRenderersMixin, PandasView):
    """Admission campaign stages by universities."""
    permission_classes = [CuratorAccessPermission]
    serializer_class = SimpleSerializer
    pandas_serializer_class = CampaignResultsByUniversitiesSerializer

    def get_queryset(self):
        campaign_id = self.kwargs.get('campaign_id')
        qs = (Applicant.objects
              .filter(campaign_id=campaign_id,
                      status__in=STATUSES)
              .values('university_id', 'university__name', 'status')
              .annotate(total=Count("status")))
        return qs


class CampaignResultsByCourses(ListRenderersMixin, PandasView):
    permission_classes = [CuratorAccessPermission]
    serializer_class = SimpleSerializer
    pandas_serializer_class = CampaignResultsByCoursesSerializer

    def get_queryset(self):
        campaign_id = self.kwargs.get('campaign_id')
        qs = (Applicant.objects
              .filter(campaign_id=campaign_id,
                      status__in=STATUSES)
              .values('course', 'status')
              .annotate(total=Count("status")))
        return qs


class CampaignStatsStudentsResults(ReadOnlyModelViewSet):
    """
    Students academic progress who enrolled in provided admission campaign.
    """
    permission_classes = [CuratorAccessPermission]

    def list(self, request, *args, **kwargs):
        return Response({})


class CampaignStatsTestingScoreByUniversities(ListRenderersMixin, PandasView):
    """Distribution of online test results by universities."""
    permission_classes = [CuratorAccessPermission]
    serializer_class = SimpleSerializer
    pandas_serializer_class = ScoreByUniversitiesSerializer

    def get_queryset(self):
        campaign_id = self.kwargs.get('campaign_id')
        return (Test.objects
                .filter(applicant__campaign_id=campaign_id)
                .values('score', 'applicant__university__name')
                .annotate(total=Count('score')))


class CampaignStatsTestingScoreByCourses(ListRenderersMixin, PandasView):
    """Distribution of online test results by courses."""
    permission_classes = [CuratorAccessPermission]
    serializer_class = SimpleSerializer
    pandas_serializer_class = ScoreByCoursesSerializer

    def get_queryset(self):
        campaign_id = self.kwargs.get('campaign_id')
        return (Test.objects
                .filter(applicant__campaign_id=campaign_id)
                .values('score', 'applicant__course')
                .annotate(total=Count('score'))
                .order_by('applicant__course'))


class CampaignStatsExamScoreByUniversities(ListRenderersMixin, PandasView):
    """Distribution of exam results by universities."""
    permission_classes = [CuratorAccessPermission]
    serializer_class = SimpleSerializer
    pandas_serializer_class = ScoreByUniversitiesSerializer

    def get_queryset(self):
        campaign_id = self.kwargs.get('campaign_id')
        return (Exam.objects
                .filter(applicant__campaign_id=campaign_id)
                .values('score', 'applicant__university__name')
                .annotate(total=Count('score')))


class CampaignStatsExamScoreByCourses(ListRenderersMixin, PandasView):
    """Distribution of exam results by courses."""
    permission_classes = [CuratorAccessPermission]
    serializer_class = SimpleSerializer
    pandas_serializer_class = ScoreByCoursesSerializer

    def get_queryset(self):
        campaign_id = self.kwargs.get('campaign_id')
        return (Exam.objects
                .filter(applicant__campaign_id=campaign_id)
                .values('score', 'applicant__course')
                .annotate(total=Count('score'))
                .order_by('applicant__course'))


class ApplicationSubmission(ListRenderersMixin, PandasView):
    """Application submission by day in UTC timezone"""
    permission_classes = [CuratorAccessPermission]
    serializer_class = SimpleSerializer
    pandas_serializer_class = ApplicationSubmissionPandasSerializer

    def get_queryset(self):
        campaign_id = self.kwargs.get('campaign_id')
        return (Applicant.objects
                .filter(campaign_id=campaign_id)
                .annotate(date=TruncDate('created'))
                .values('date')
                .annotate(total=Count('date'))
                .order_by('date'))
