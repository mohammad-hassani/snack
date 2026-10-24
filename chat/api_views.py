"""JSON account endpoints for the Next.js client; Django owns authentication."""
import json
import logging
from smtplib import SMTPException
from datetime import timedelta
from functools import wraps
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.cache import never_cache
from .forms import LoginForm, SignupForm
from .models import Invitation, Membership, Workspace
from .services import display_name, provision_workspace, rate_limit
from .views import api, text_field


def public_api(methods):
    def decorate(view):
        @wraps(view)
        @never_cache
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                return JsonResponse({'error': 'این روش درخواست مجاز نیست.'}, status=405)
            try:
                request.data = json.loads(request.body or '{}')
                if not isinstance(request.data, dict) or any(not isinstance(v, str) for v in request.data.values()):
                    raise ValidationError('داده‌های فرم باید متن باشند.')
                return view(request, *args, **kwargs)
            except (ValidationError, ValueError, TypeError) as error:
                return JsonResponse({'error': ' '.join(error.messages) if isinstance(error, ValidationError) else 'درخواست نامعتبر است.'}, status=400)
        return wrapped
    return decorate


def form_error(form):
    return JsonResponse({'error': ' '.join(str(e) for errors in form.errors.values() for e in errors), 'fields': form.errors}, status=400)


@public_api(['GET'])
def session(request):
    user = request.user
    return JsonResponse({'csrfToken': get_token(request), 'user': {'id': user.pk, 'name': display_name(user), 'email': user.email} if user.is_authenticated else None, 'workspaces': list(Workspace.objects.filter(memberships__user=user).values('id', 'name')) if user.is_authenticated else []})


@public_api(['POST'])
def sign_in(request):
    form = LoginForm(request, data=request.data)
    if not form.is_valid():
        return form_error(form)
    login(request, form.get_user())
    return JsonResponse({'ok': True, 'csrfToken': get_token(request)})


@public_api(['POST'])
def sign_up(request):
    rate_limit(f'signup:{request.META.get("REMOTE_ADDR", "unknown")}', 10, 3600)
    form = SignupForm(request.data)
    if not form.is_valid():
        return form_error(form)
    try:
        with transaction.atomic():
            user = form.save()
    except IntegrityError:
        return JsonResponse({'error': 'حسابی با این ایمیل وجود دارد.'}, status=409)
    login(request, user)
    return JsonResponse({'ok': True, 'csrfToken': get_token(request)}, status=201)


@public_api(['POST'])
def sign_out(request):
    logout(request)
    return JsonResponse({'ok': True})


@never_cache
@api
def workspaces(request):
    if request.method == 'GET':
        return JsonResponse({'workspaces': list(Workspace.objects.filter(memberships__user=request.user).values('id', 'name'))})
    if request.method != 'POST':
        return JsonResponse({'error': 'این روش درخواست مجاز نیست.'}, status=405)
    workspace = provision_workspace(request.user, text_field(request.data, 'name'))
    return JsonResponse({'id': workspace.pk, 'name': workspace.name}, status=201)


@never_cache
@api
def invitation(request, token):
    if request.method not in ('GET', 'POST'):
        return JsonResponse({'error': 'این روش درخواست مجاز نیست.'}, status=405)
    with transaction.atomic():
        invite = get_object_or_404(Invitation.objects.select_for_update().select_related('workspace'), token=token)
        if invite.accepted_at or invite.created_at < timezone.now() - timedelta(days=7):
            raise ValidationError('این دعوت‌نامه منقضی شده یا قبلاً پذیرفته شده است.')
        if request.user.email.lower() != invite.email.lower():
            return JsonResponse({'error': f'با ایمیل {invite.email} وارد شوید.'}, status=403)
        if request.method == 'POST':
            Membership.objects.get_or_create(workspace=invite.workspace, user=request.user)
            invite.accepted_at = timezone.now()
            invite.save(update_fields=['accepted_at'])
        return JsonResponse({'workspace': invite.workspace.name, 'workspace_id': invite.workspace_id})


@public_api(['POST'])
def password_reset(request):
    rate_limit(f'reset:{request.META.get("REMOTE_ADDR", "unknown")}', 10, 3600)
    form = PasswordResetForm(request.data)
    if not form.is_valid():
        return form_error(form)
    try:
        form.save(request=request, domain_override=urlsplit(settings.FRONTEND_URL).netloc or None, use_https=settings.FRONTEND_URL.startswith('https:') if settings.FRONTEND_URL else request.is_secure(), email_template_name='registration/password_reset_email.html', subject_template_name='registration/password_reset_subject.txt')
    except (SMTPException, OSError):
        # Keep the same response for existing and unknown accounts.
        logging.getLogger(__name__).warning('Password reset email delivery failed')
    return JsonResponse({'ok': True})


@public_api(['POST'])
def password_confirm(request, uidb64, token):
    try:
        user = get_user_model().objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (ValueError, TypeError, UnicodeDecodeError, OverflowError, get_user_model().DoesNotExist):
        user = None
    if user is None or not default_token_generator.check_token(user, token):
        raise ValidationError('پیوند بازنشانی نامعتبر یا منقضی شده است.')
    form = SetPasswordForm(user, request.data)
    if not form.is_valid():
        return form_error(form)
    form.save()
    return JsonResponse({'ok': True})


def csrf_failure(request, reason=''):
    return JsonResponse({'error': 'نشست امنیتی معتبر نیست. صفحه را تازه کنید.'}, status=403)
