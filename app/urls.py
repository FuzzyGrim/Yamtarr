from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

from decouple import config
from . import views

urlpatterns = [
    path("", views.home, name = "home"),
    path("search", views.search, name = "search"),
    path("profile/", views.profile, name = "profile"),
    path("login/", views.login, name = "login"),
    path("logout/", auth_views.LogoutView.as_view(), name = "logout"),
    path("edit/<str:media_type>/<int:media_id>/", views.edit, name = "edit"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if config("REGISTRATION", default = False, cast=bool):
    urlpatterns.append(path("register/", views.register, name = "register"))