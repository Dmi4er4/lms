# -*- coding: utf-8 -*-

from collections import OrderedDict
from decimal import Decimal
import json

from import_export import fields, resources, widgets
from import_export.instance_loaders import CachedInstanceLoader
from import_export.widgets import IntegerWidget

from admission.constants import ChallengeStatuses
from admission.models import Exam, Olympiad, Test

# XXX: Not tested with django-import-export==1.0.1


class JsonFieldWidget(widgets.Widget):    

    def clean(self, value, row=None, *args, **kwargs):
        value = super(JsonFieldWidget, self).clean(value)
        if value and isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    def render(self, value, obj=None):
        if value:
            if isinstance(value, dict) or isinstance(value, list):
                return json.dumps(value)
            return str(value)
        return ""


class ContestDetailsMixin:
    # Other fields will be aggregated to the `details` json field
    known_fields = (
        "created",
        "applicant",
        "yandex_login",
        "score",
        "status",
    )

    def before_import(self, data, using_transactions, dry_run, **kwargs):
        if "details" in data.headers:
            del data["details"]
        data.append_col(self.row_collect_details(data.headers), header="details")

    def before_import_row(self, row, **kwargs):
        for k, v in row.items():
            if v == "None":
                row[k] = ""
        super().before_import_row(row, **kwargs)

    def row_collect_details(self, headers):
        """Collect data for `details` column"""

        def wrapper(row):
            details = OrderedDict()
            for i, h in enumerate(headers):
                if h not in self.known_fields:
                    details[h] = row[i]
            # All column values with pattern in a header go
            # to the `scores` attribute
            if details:
                to_delete = []
                scores = []
                patterns = ("Задача", "Задание")
                for k, v in details.items():
                    if any(p in k for p in patterns):
                        to_delete.append(k)
                        scores.append(v)
                for k in to_delete:
                    del details[k]
                if scores:
                    details["scores"] = scores
            return details

        return wrapper


class OnlineTestRecordResource(ContestDetailsMixin, resources.ModelResource):
    applicant = fields.Field(
        column_name="applicant", attribute="applicant_id", widget=IntegerWidget()
    )
    details = fields.Field(
        column_name="details", attribute="details", widget=JsonFieldWidget()
    )
    # Note: It returns __str__ representation of `applicant` attribute
    fio = fields.Field(column_name="fio", attribute="applicant")
    yandex_login = fields.Field(
        column_name="yandex_login", attribute="applicant__yandex_login"
    )
    status = fields.Field(
        column_name="status", attribute="status", default=ChallengeStatuses.MANUAL
    )

    class Meta:
        model = Test
        import_id_fields = ("applicant",)
        skip_unchanged = True

    def skip_row(self, instance, original):
        # Leave the lowest score
        if original.score and instance.score:
            return instance.score > original.score
        return super().skip_row(instance, original)


# FIXME: RowResult.obj_repr calls Exam.__str__ which makes additional db hits
class ExamRecordResource(ContestDetailsMixin, resources.ModelResource):
    applicant = fields.Field(
        column_name="applicant", attribute="applicant_id", widget=IntegerWidget()
    )

    details = fields.Field(
        column_name="details", attribute="details", widget=JsonFieldWidget()
    )

    class Meta:
        model = Exam
        import_id_fields = ("applicant",)
        skip_unchanged = True
        fields = ("applicant", "score", "status", "details")
        instance_loader_class = CachedInstanceLoader

    def before_import_row(self, row, **kwargs):
        """Double check that score is always a valid type, on DB level we
        can have null value, so if we omit django field validation on client,
        it will be very bad"""
        assert int(Decimal(row["score"])) >= 0


class OlympiadResource(ContestDetailsMixin, resources.ModelResource):
    applicant = fields.Field(
        column_name="applicant", attribute="applicant_id", widget=IntegerWidget()
    )

    details = fields.Field(
        column_name="details", attribute="details", widget=JsonFieldWidget()
    )

    class Meta:
        model = Olympiad
        import_id_fields = ("applicant",)
        skip_unchanged = True
        fields = ("applicant", "score", "math_score", "status", "details")
        instance_loader_class = CachedInstanceLoader
        
    def dehydrate_details(self, obj):
        return json.dumps(obj.details)
    
    def hydrate_details(self, value):
        if value and isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value
        
    def before_import(self, data, using_transactions, dry_run, **kwargs):
        if "details" in data.headers:
            for element in data["details"]:
                element = self.hydrate_details(element)

    def before_import_row(self, row, **kwargs):
        """Double check that score is always a valid type, on DB level we
        can have null value, so if we omit django field validation on client,
        it will be very bad"""
        if row.get("score"):
            assert int(Decimal(row["score"])) >= 0
        if row.get("math_score"):
            assert int(Decimal(row["math_score"])) >= 0
