import time
import uuid
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import Channel, ChannelMember, Membership, Message, Workspace


def accessible_channels(user, workspace_id):
    if not Membership.objects.filter(user=user, workspace_id=workspace_id).exists():
        raise PermissionDenied
    return Channel.objects.filter(workspace_id=workspace_id).filter(Q(kind='public') | Q(members__user=user)).distinct()


def channel_for(user, channel_id):
    channel = Channel.objects.get(pk=channel_id)
    if not accessible_channels(user, channel.workspace_id).filter(pk=channel.pk).exists():
        raise PermissionDenied
    return channel


def rate_limit(key, limit=60, seconds=60):
    bucket = f'rate:{key}:{int(time.time()) // seconds}'
    cache.add(bucket, 0, seconds + 1)
    if cache.incr(bucket) > limit:
        raise ValidationError('تعداد درخواست‌ها زیاد است. کمی صبر کنید و دوباره تلاش کنید.')


def display_name(user):
    return user.first_name or user.username


def serialize_message(message):
    data = {'id': message.id, 'channel_id': message.channel_id, 'sender_id': message.sender_id, 'sender': display_name(message.sender), 'body': '' if message.deleted else message.body, 'created_at': message.created_at.isoformat(), 'edited_at': message.edited_at.isoformat() if message.edited_at else None, 'deleted': message.deleted, 'client_message_id': str(message.client_message_id), 'reply_to': message.reply_to_id}
    if not message.deleted and hasattr(message, 'attachment'):
        data['attachment'] = {'name': message.attachment.name, 'size': message.attachment.size, 'url': f'/files/{message.attachment.id}/'}
    return data


def broadcast(target_channel_id, event, **data):
    async_to_sync(get_channel_layer().group_send)(f'channel_{target_channel_id}', {'type': 'chat.event', 'event': event, **data})


def send_message(user, channel_id, body, client_message_id, reply_to=None, upload=None):
    channel = channel_for(user, channel_id)
    if not isinstance(body, str) or len(body) > 4000 or (not body.strip() and not upload):
        raise ValidationError('پیامی با ۱ تا ۴۰۰۰ نویسه بنویسید یا فایلی پیوست کنید.')
    try:
        client_id = uuid.UUID(str(client_message_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('شناسهٔ معتبر برای پیام الزامی است.')
    if reply_to:
        try:
            reply_to = int(reply_to)
        except (ValueError, TypeError):
            raise ValidationError('پاسخ نامعتبر است.')
    if reply_to and not Message.objects.filter(pk=reply_to, channel=channel).exists():
        raise ValidationError('پیام پاسخ باید متعلق به همین گفتگو باشد.')
    if upload:
        validate_upload(upload)
    with transaction.atomic():
        # Serialize sends in each conversation so cursor recovery follows commit order.
        Channel.objects.select_for_update().get(pk=channel.pk)
        message, created = Message.objects.get_or_create(channel=channel, sender=user, client_message_id=client_id, defaults={'body': body.strip(), 'reply_to_id': reply_to})
        if created:
            rate_limit(f'send:{user.pk}')
            if upload:
                from .models import Attachment
                Attachment.objects.create(message=message, file=upload, name=upload.name[:200], content_type=upload.content_type or 'application/octet-stream', size=upload.size)
            transaction.on_commit(lambda: broadcast(channel.pk, 'new:message', message=serialize_message(message)))
    return message


def validate_upload(upload):
    from pathlib import Path
    if upload.size > 10 * 1024 * 1024:
        raise ValidationError('حجم فایل باید حداکثر ۱۰ مگابایت باشد.')
    allowed = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.txt', '.csv', '.md', '.zip'}
    if Path(upload.name).suffix.lower() not in allowed:
        raise ValidationError('فایل تصویر، PDF، متن، CSV، Markdown یا ZIP انتخاب کنید.')
    if Path(upload.name).suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}:
        from PIL import Image
        try:
            Image.open(upload).verify()
            upload.seek(0)
        except Exception:
            raise ValidationError('این تصویر معتبر نیست.')


def mutate_message(user, message_id, body=None, delete=False):
    message = Message.objects.select_related('sender', 'channel').get(pk=message_id)
    channel_for(user, message.channel_id)
    is_admin = Membership.objects.filter(workspace=message.channel.workspace, user=user, role='admin').exists()
    if message.sender_id != user.id and not (delete and is_admin):
        raise PermissionDenied
    if delete:
        message.deleted = True
        message.body = ''
    else:
        if message.deleted or not isinstance(body, str) or not body.strip() or len(body) > 4000:
            raise ValidationError('پیامی با ۱ تا ۴۰۰۰ نویسه بنویسید.')
        message.body = body.strip()
        message.edited_at = timezone.now()
    message.save()
    broadcast(message.channel_id, 'deleted:message' if delete else 'updated:message', message=serialize_message(message))
    return message


def mark_read(user, channel_id, message_id):
    channel = channel_for(user, channel_id)
    if not Message.objects.filter(channel=channel, pk=message_id).exists():
        raise ValidationError('موقعیت خواندن پیام نامعتبر است.')
    member, _ = ChannelMember.objects.get_or_create(channel=channel, user=user)
    ChannelMember.objects.filter(pk=member.pk, last_read_id__lt=message_id).update(last_read_id=message_id)


def provision_workspace(user, name):
    from django.utils.text import slugify
    if not name or len(name) > 80:
        raise ValidationError('نام فضای کاری باید بین ۱ تا ۸۰ نویسه باشد.')
    with transaction.atomic():
        workspace = Workspace.objects.create(name=name, slug=f'{slugify(name)[:40] or "team"}-{uuid.uuid4().hex[:8]}')
        Membership.objects.create(workspace=workspace, user=user, role='admin')
        for channel_name, description in [('general', 'جایی برای خبرهای تیم، پرسش‌ها و گفتگوهای خوب.'), ('introductions', 'خودتان را معرفی کنید و با هم‌تیمی‌ها آشنا شوید.')]:
            channel = Channel.objects.create(workspace=workspace, name=channel_name, description=description, created_by=user)
            ChannelMember.objects.create(channel=channel, user=user)
    return workspace
