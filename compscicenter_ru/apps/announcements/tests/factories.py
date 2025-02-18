import factory
import pytz

from announcements.models import Announcement, AnnouncementEventDetails, AnnouncementTag

__all__ = ('AnnouncementTagFactory', 'AnnouncementFactory',
           'AnnouncementEventDetailsFactory')


class AnnouncementTagFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: "Tag %04d" % n)
    slug = factory.Sequence(lambda n: "slug-%04d" % n)

    class Meta:
        model = AnnouncementTag


class AnnouncementFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: "Announcement %04d" % n)
    slug = factory.Sequence(lambda n: "slug-%04d" % n)
    short_description = factory.Sequence(lambda n: "Short description %04d" % n)
    publish_end_at = factory.Faker('future_datetime', end_date="+30d",
                                   tzinfo=pytz.UTC)

    class Meta:
        model = Announcement

    @factory.post_generation
    def tags(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for tag in extracted:
                self.tags.add(tag)


class AnnouncementEventDetailsFactory(factory.django.DjangoModelFactory):
    announcement = factory.SubFactory(AnnouncementFactory)
    ends_on = factory.Faker('future_date', end_date="+30d")

    class Meta:
        model = AnnouncementEventDetails
