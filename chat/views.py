import json
import logging
from smtplib import SMTPException
from datetime import timedelta
from functools import wraps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.cache import never_cache
from .forms import SignupForm
from .models import Attachment, Channel, ChannelMember, Invitation, Membership, Message, Workspace
from .services import accessible_channels, channel_for, display_name, mark_read, mutate_message, rate_limit, send_message, serialize_message, provision_workspace


def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            rate_limit(f'signup:{request.META.get("REMOTE_ADDR", "unknown")}', 10, 3600)
            with transaction.atomic():
                user = form.save()
        except ValidationError as error:
            form.add_error(None, error)
        except IntegrityError:
            form.add_error('email', 'حسابی با این ایمیل وجود دارد.')
        else:
            login(request, user)
            target = request.GET.get('next', '/')
            return redirect(target if url_has_allowed_host_and_scheme(target, {request.get_host()}, require_https=request.is_secure()) else '/')
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def home(request):
    workspaces = Workspace.objects.filter(memberships__user=request.user)
    if not workspaces.exists():
        return render(request, 'onboarding.html')
    requested = request.GET.get('workspace')
    workspace = get_object_or_404(workspaces, pk=requested) if requested else workspaces.first()
    return render(request, 'chat.html', {'workspace': workspace, 'workspaces': workspaces})


@login_required
@require_POST
def create_workspace(request):
    name = request.POST.get('name', '').strip()
    if not name or len(name) > 80:
        messages.error(request, 'نام فضای کاری باید بین ۱ تا ۸۰ نویسه باشد.')
        return redirect('home')
    workspace = provision_workspace(request.user, name)
    return redirect(f'/?workspace={workspace.pk}')


def api(view):
    @wraps(view)
    @never_cache
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'لطفاً وارد حساب شوید.'}, status=401)
        try:
            request.data = json.loads(request.body or '{}') if request.content_type == 'application/json' else request.POST
            if not isinstance(request.data, dict) and request.content_type == 'application/json':
                raise ValidationError('دادهٔ درخواست باید یک شیء JSON باشد.')
            response = view(request, *args, **kwargs)
            if response.status_code == 405:
                return JsonResponse({'error': 'این روش درخواست مجاز نیست.'}, status=405)
            return response
        except PermissionDenied:
            return JsonResponse({'error': 'به این گفتگو یا فضای کاری دسترسی ندارید.'}, status=403)
        except (ValidationError, ValueError, TypeError) as error:
            return JsonResponse({'error': ' '.join(error.messages) if isinstance(error, ValidationError) else 'درخواست نامعتبر است.'}, status=400)
        except (Http404, Channel.DoesNotExist, Message.DoesNotExist, Workspace.DoesNotExist):
            return JsonResponse({'error': 'یافت نشد.'}, status=404)
        except IntegrityError:
            return JsonResponse({'error': 'این نام قبلاً استفاده شده است.'}, status=409)
    return wrapped


def text_field(data, key, default=''):
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ValidationError(f'مقدار {key} باید متن باشد.')
    return value.strip()


def admin_membership(user, workspace_id):
    return get_object_or_404(Membership, user=user, workspace_id=workspace_id, role='admin')


@api
@require_GET
def bootstrap(request, workspace_id):
    channels = accessible_channels(request.user, workspace_id).order_by('kind', 'name')
    result = []
    for channel in channels:
        cm = ChannelMember.objects.filter(channel=channel, user=request.user).first()
        other = channel.members.exclude(user=request.user).select_related('user').first() if channel.kind == 'dm' else None
        result.append({'id': channel.id, 'name': display_name(other.user) if other else channel.name, 'kind': channel.kind, 'description': channel.description, 'unread': channel.messages.filter(id__gt=cm.last_read_id if cm else 0, deleted=False).exclude(sender=request.user).count()})
    members = Membership.objects.filter(workspace_id=workspace_id).select_related('user')
    return JsonResponse({'me': {'id': request.user.id, 'name': display_name(request.user), 'role': members.get(user=request.user).role}, 'channels': result, 'members': [{'id': m.user_id, 'name': display_name(m.user), 'email': m.user.email, 'role': m.role, 'online': bool(cache.get(f'presence:{m.user_id}'))} for m in members]})


@api
@require_POST
def create_channel(request, workspace_id):
    accessible_channels(request.user, workspace_id)
    name = text_field(request.data, 'name').lower()
    kind = request.data.get('kind', 'public')
    if not name or len(name) > 80 or kind not in ('public', 'private'):
        raise ValidationError('نام کانال (حداکثر ۸۰ نویسه) و نوع دسترسی عمومی یا خصوصی را مشخص کنید.')
    description = text_field(request.data, 'description')
    if len(description) > 240:
        raise ValidationError('توضیحات باید حداکثر ۲۴۰ نویسه باشد.')
    member_ids = request.data.get('members', [])
    if not isinstance(member_ids, list):
        raise ValidationError('اعضای فضای کاری را انتخاب کنید.')
    member_ids = set(int(value) for value in member_ids) | {request.user.pk}
    if Membership.objects.filter(workspace_id=workspace_id, user_id__in=member_ids).count() != len(member_ids):
        raise ValidationError('فقط اعضای همین فضای کاری را انتخاب کنید.')
    with transaction.atomic():
        channel = Channel.objects.create(workspace_id=workspace_id, created_by=request.user, name=name, kind=kind, description=description)
        ChannelMember.objects.bulk_create([ChannelMember(channel=channel, user_id=pk) for pk in member_ids])
    return JsonResponse({'id': channel.id}, status=201)


@api
@require_POST
def direct_message(request, workspace_id):
    accessible_channels(request.user, workspace_id)
    target = get_object_or_404(Membership, workspace_id=workspace_id, user_id=request.data.get('user_id')).user
    if target == request.user:
        raise ValidationError('یک هم‌تیمی دیگر را انتخاب کنید.')
    key = ':'.join(str(pk) for pk in sorted([target.pk, request.user.pk]))
    with transaction.atomic():
        channel, _ = Channel.objects.get_or_create(workspace_id=workspace_id, dm_key=key, defaults={'name': f'dm-{key}', 'kind': 'dm', 'created_by': request.user})
        for user in (target, request.user):
            ChannelMember.objects.get_or_create(channel=channel, user=user)
    return JsonResponse({'id': channel.id})


@api
def channel_messages(request, channel_id):
    channel = channel_for(request.user, channel_id)
    if request.method == 'POST':
        message = send_message(request.user, channel.id, request.data.get('body', ''), request.data.get('client_message_id'), request.data.get('reply_to') or None, request.FILES.get('file'))
        return JsonResponse({'message': serialize_message(message)}, status=201)
    if request.method != 'GET':
        return JsonResponse({'error': 'این روش درخواست مجاز نیست.'}, status=405)
    queryset = channel.messages.select_related('sender', 'attachment')
    before, after = request.GET.get('before'), request.GET.get('after')
    if before:
        queryset = queryset.filter(id__lt=int(before))
    if after:
        queryset = queryset.filter(id__gt=int(after))
        rows = list(queryset.order_by('id')[:51])
        page = rows[:50]
    else:
        rows = list(queryset.order_by('-id')[:51])
        page = list(reversed(rows[:50]))
    return JsonResponse({'messages': [serialize_message(m) for m in page], 'has_more': len(rows) > 50})


@api
def message_detail(request, message_id):
    if request.method not in ('PATCH', 'DELETE'):
        return JsonResponse({'error': 'این روش درخواست مجاز نیست.'}, status=405)
    message = mutate_message(request.user, message_id, request.data.get('body'), request.method == 'DELETE')
    return JsonResponse({'message': serialize_message(message)})


@api
@require_POST
def read_channel(request, channel_id):
    mark_read(request.user, channel_id, int(request.data.get('message_id', 0)))
    return JsonResponse({'ok': True})


@api
@require_GET
def search(request, workspace_id):
    channels = accessible_channels(request.user, workspace_id)
    query = request.GET.get('q', '').strip()
    if not 2 <= len(query) <= 100:
        raise ValidationError('عبارت جستجو باید بین ۲ تا ۱۰۰ نویسه باشد.')
    found = Message.objects.filter(channel__in=channels, deleted=False, body__icontains=query).select_related('sender', 'channel', 'attachment').order_by('-id')[:50]
    return JsonResponse({'messages': [{**serialize_message(m), 'channel_name': m.channel.name} for m in found]})


@api
@require_POST
def invite(request, workspace_id):
    member = admin_membership(request.user, workspace_id)
    from django.core.validators import validate_email
    email = text_field(request.data, 'email').lower()
    validate_email(email)
    rate_limit(f'invite:{request.user.pk}', 20, 3600)
    invitation = Invitation.objects.create(workspace=member.workspace, email=email, invited_by=request.user)
    link = f'{settings.FRONTEND_URL}/invite/{invitation.token}/' if settings.FRONTEND_URL else request.build_absolute_uri(f'/invite/{invitation.token}/')
    try:
        send_mail(f'دعوت به {member.workspace.name} در اسنک', f'شما به {member.workspace.name} دعوت شده‌اید. تا هفت روز فرصت پذیرش دارید: {link}', None, [email])
    except (SMTPException, OSError):
        logging.getLogger(__name__).warning('Invitation email delivery failed for workspace %s', workspace_id)
        return JsonResponse({'error': 'ارسال ایمیل دعوت‌نامه ممکن نشد. تنظیمات ایمیل را بررسی و دوباره تلاش کنید.'}, status=503)
    return JsonResponse({'url': link, 'email': email}, status=201)


@login_required
def accept_invite(request, token):
    invitation = get_object_or_404(Invitation, token=token)
    if invitation.created_at < timezone.now() - timedelta(days=7) or invitation.accepted_at:
        return render(request, 'invite.html', {'error': 'این دعوت‌نامه منقضی شده یا قبلاً پذیرفته شده است.'}, status=400)
    if request.user.email.lower() != invitation.email.lower():
        return render(request, 'invite.html', {'error': f'برای پذیرش این دعوت‌نامه با ایمیل {invitation.email} وارد شوید.'}, status=403)
    if request.method == 'POST':
        with transaction.atomic():
            Membership.objects.get_or_create(workspace=invitation.workspace, user=request.user)
            invitation.accepted_at = timezone.now()
            invitation.save()
        return redirect(f'/?workspace={invitation.workspace_id}')
    return render(request, 'invite.html', {'invitation': invitation})


@api
@require_POST
def manage_member(request, workspace_id, user_id):
    admin_membership(request.user, workspace_id)
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=workspace_id)
        member = get_object_or_404(Membership, workspace_id=workspace_id, user_id=user_id)
        role = request.data.get('role')
        if role not in ('admin', 'member', 'remove'):
            raise ValidationError('عملیات تغییر نقش به مدیر، عضو یا حذف را انتخاب کنید.')
        if member.role == 'admin' and role != 'admin' and Membership.objects.filter(workspace_id=workspace_id, role='admin').count() == 1:
            raise ValidationError('فضای کاری باید دست‌کم یک مدیر داشته باشد.')
        if role == 'remove':
            ChannelMember.objects.filter(channel__workspace_id=workspace_id, user_id=user_id).delete()
            member.delete()
        else:
            member.role = role
            member.save()
    return JsonResponse({'ok': True})


@login_required
def download(request, attachment_id):
    attachment = get_object_or_404(Attachment.objects.select_related('message'), pk=attachment_id, message__deleted=False)
    channel_for(request.user, attachment.message.channel_id)
    response = FileResponse(attachment.file.open('rb'), as_attachment=True, filename=attachment.name, content_type='application/octet-stream')
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


def health(request):
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return JsonResponse({'status': 'ok'})
