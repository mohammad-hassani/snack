from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from channels.auth import get_user
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from .models import Channel
from .services import accessible_channels, broadcast, channel_for, display_name, mark_read, mutate_message, rate_limit, send_message, serialize_message


class ChatConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.user = self.scope['user']
        self.workspace_id = self.scope['url_route']['kwargs']['workspace_id']
        self.groups_joined = set()
        if not self.user.is_authenticated:
            self.close(code=4401)
            return
        try:
            channels = list(accessible_channels(self.user, self.workspace_id))
        except PermissionDenied:
            self.close(code=4403)
            return
        self.accept()
        self.join_channels(channels)
        self.presence()
        self.send_json({'event': 'ready'})

    def join_channels(self, channels):
        for channel in channels:
            group = f'channel_{channel.pk}'
            if group not in self.groups_joined:
                async_to_sync(self.channel_layer.group_add)(group, self.channel_name)
                self.groups_joined.add(group)

    def authorized(self):
        if not Session.objects.filter(session_key=self.scope['session'].session_key, expire_date__gt=timezone.now()).exists():
            self.close(code=4401)
            return False
        fresh_user = async_to_sync(get_user)(self.scope)
        if not fresh_user.is_authenticated or not fresh_user.is_active:
            self.close(code=4401)
            return False
        return True

    def presence(self):
        # shortcut: heartbeat presence expires after 45 seconds; use dedicated presence storage for large teams.
        was_online = cache.get(f'presence:{self.user.pk}')
        cache.set(f'presence:{self.user.pk}', True, 45)
        if not was_online:
            for channel in accessible_channels(self.user, self.workspace_id):
                broadcast(channel.pk, 'update:presence', channel_id=channel.pk, user_id=self.user.pk, online=True)

    def receive(self, text_data=None, bytes_data=None, **kwargs):
        if bytes_data is not None or text_data is None or len(text_data) > 16384:
            self.send_json({'event': 'error', 'error': 'رویداد بیش از حد بزرگ یا نامعتبر است.'})
            return
        try:
            super().receive(text_data=text_data, **kwargs)
        except ValueError:
            self.send_json({'event': 'error', 'error': 'دادهٔ JSON نامعتبر است.'})

    def receive_json(self, content, **kwargs):
        if not self.authorized():
            return
        try:
            if not isinstance(content, dict):
                raise ValidationError('دادهٔ رویداد باید یک شیء باشد.')
            rate_limit(f'ws:{self.user.pk}', 180)
            event = content.get('event')
            if event == 'ping':
                self.join_channels(accessible_channels(self.user, self.workspace_id))
                self.presence()
                self.send_json({'event': 'pong'})
                return
            channel_id = int(content.get('channel_id', 0))
            channel = channel_for(self.user, channel_id)
            if channel.workspace_id != self.workspace_id:
                raise PermissionDenied
            if event == 'send:message':
                message = send_message(self.user, channel_id, content.get('body', ''), content.get('client_message_id'), content.get('reply_to'))
                self.send_json({'event': 'ack:message', 'message': serialize_message(message)})
            elif event in ('edit:message', 'delete:message'):
                from .models import Message
                if not Message.objects.filter(pk=content.get('message_id'), channel=channel).exists():
                    raise ValidationError('پیام نامعتبر است.')
                mutate_message(self.user, content.get('message_id'), content.get('body'), event == 'delete:message')
            elif event in ('start:typing', 'stop:typing'):
                broadcast(channel_id, event, channel_id=channel_id, user_id=self.user.pk, name=display_name(self.user))
            elif event == 'read:message':
                mark_read(self.user, channel_id, int(content.get('message_id', 0)))
            else:
                raise ValidationError('رویداد ناشناخته است.')
        except (PermissionDenied, Channel.DoesNotExist):
            self.send_json({'event': 'error', 'error': 'به این گفتگو دسترسی ندارید.'})
        except (ValidationError, ValueError, TypeError) as error:
            self.send_json({'event': 'error', 'error': ' '.join(error.messages) if isinstance(error, ValidationError) else 'رویداد نامعتبر است.'})

    def chat_event(self, event):
        if event.get('event') == 'update:presence' and event.get('user_id') == self.user.pk:
            return
        if not self.authorized():
            return
        message = event.get('message')
        channel_id = message['channel_id'] if message else event.get('channel_id')
        try:
            channel_for(self.user, channel_id)
        except (PermissionDenied, Channel.DoesNotExist):
            return
        self.send_json({key: value for key, value in event.items() if key != 'type'})

    def disconnect(self, code):
        for group in getattr(self, 'groups_joined', set()):
            async_to_sync(self.channel_layer.group_discard)(group, self.channel_name)
