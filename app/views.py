from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import (
    update_session_auth_hash,
    authenticate,
    login as auth_login,
)
from django.contrib.auth.forms import PasswordChangeForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import JsonResponse
from django.conf import settings
from django.template.loader import render_to_string


from app.models import Media
from app.forms import UserRegisterForm, UserUpdateForm
from app.utils import database, interactions


@login_required
def home(request):
    if request.method == "POST":
        if "delete" in request.POST:
            Media.objects.get(
                media_id=request.POST["delete"],
                user=request.user,
                api=request.POST["api"],
            ).delete()
        elif "status" in request.POST:
            database.edit_media(request)

        return redirect("home")

    queryset = Media.objects.filter(user_id=request.user)
    data = {
        "tv": {"media": [], "statuses": {}},
        "movie": {"media": [], "statuses": {}},
        "anime": {"media": [], "statuses": {}},
        "manga": {"media": [], "statuses": {}},
    }
    for media in queryset:
        media_type = media.media_type
        data[media_type]["media"].append(media)
        status = (media.status).lower()
        if status not in data[media_type]["statuses"]:
            data[media_type]["statuses"][status] = []
        data[media_type]["statuses"][status].append(media)
    return render(request, "app/home.html", {"data": data})


@login_required
def search(request):
    api = request.GET.get("api")
    query = request.GET.get("q")
    request.session['last_selected_api'] = api

    if request.method == "POST":
        if "delete" in request.POST:
            Media.objects.get(
                media_id=request.POST["delete"],
                user=request.user,
                api=request.POST["api"],
            ).delete()
        elif "status" in request.POST:
            if request.user.is_authenticated:
                if Media.objects.filter(
                    media_id=request.POST["media_id"],
                    user=request.user,
                    api=request.POST["api"],
                ).exists():
                    database.edit_media(request)
                else:
                    database.add_media(request)
            else:
                messages.error(request, "Log in is required to track media.")
                return redirect("login")
        return redirect("/search?api=" + api + "&q=" + query)

    query_list = interactions.search(api, query)
    context = {"query_list": query_list}
    return render(request, "app/search.html", context)


def register(request):
    form = UserRegisterForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        form.save()
        return redirect("login")
    return render(request, "app/register.html", {"form": form})


def login(request):
    form = AuthenticationForm()
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST["username"],
            password=request.POST["password"],
        )
        if user is not None:
            auth_login(request, user)
            return redirect_after_login(request)
        else:
            messages.error(
                request,
                "Please enter a correct username and password. Note that both fields may be case-sensitive.",
            )
    return render(request, "app/login.html", {"form": form})


@login_required
def profile(request):
    user_form = UserUpdateForm(request.POST or None, instance=request.user)
    password_form = PasswordChangeForm(request.user, request.POST or None)
    
    if request.method == 'POST':
        if user_form.is_valid():
            user_form.save()
            messages.success(request, "Your account has been updated!")

        elif password_form.is_valid():
            password = password_form.save()
            update_session_auth_hash(request, password)
            messages.success(request, "Your password has been updated!")

        elif request.POST.get("mal"):
            if interactions.import_myanimelist(request.POST.get("mal"), request.user):
                messages.success(request, "Your MyAnimeList has been imported!")
            else:
                messages.error(request, "User not found")

        elif request.FILES.get("tmdb"):
            if interactions.import_tmdb(request.FILES.get("tmdb"), request.user):
                messages.success(request, "Your TMDB list has been imported!")
            else:
                messages.error(
                    request,
                    'Error importing your list, make sure it\'s a CSV file containing the word "ratings" or "watchlist" in the name'
                )

        elif request.POST.get("anilist"):
            errors = interactions.import_anilist(request.POST.get("anilist"), request.user)
            if len(errors) == 0:
                messages.success(request, "Your AniList has been imported!")
            elif errors[0] == "User not found":
                messages.error(request, "User not found")
            else:
                message = "<br/>".join(errors)
                messages.error(
                    request,
                    format_html(
                        "<b>{}</b> <br>{}",
                        "Couldn't find a matching MAL ID for: ",
                        mark_safe(message),
                    ),
                )
        return redirect("profile")

    context = {"user_form": user_form, "password_form": password_form}
    return render(request, "app/profile.html", context)



def edit(request, media_type, media_id):

    if media_type in ["anime", "manga"]:
        media = interactions.mal_edit(request, media_type, media_id)
    elif media_type in ["movie", "tv"]:
        media = interactions.tmdb_edit(request, media_type, media_id)

    data = {'title': media["response"]["title"], 'year': media["response"]["year"], 'media_type': media["response"]["media_type"]}
    media['response']['media_type'] = media_type
    data['html'] = render_to_string("app/edit.html", {'media': media}, request=request)
    
    if "database" in media:
        data['in_db'] = True
        data['seasons_details'] = media["database"].seasons_details
    else:
        data['in_db'] = False

    return JsonResponse(data)


def redirect_after_login(request):
    next = request.GET.get("next", None)
    if next is None:
        return redirect(settings.LOGIN_REDIRECT_URL)
    elif not url_has_allowed_host_and_scheme(
            url=next,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure()):
        return redirect(settings.LOGIN_REDIRECT_URL)
    else:
        return redirect(next)