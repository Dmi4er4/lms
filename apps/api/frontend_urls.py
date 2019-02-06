from django.conf.urls import include, url

app_name = 'api'

urlpatterns = [
    url(r'^v2/', include('courses.api.urls')),
    url(r'^v2/', include('learning.api.urls')),
]