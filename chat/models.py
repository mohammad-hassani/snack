import uuid
from django.conf import settings
from django.db import models


class Workspace(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=[('admin', 'Admin'), ('member', 'Member')], default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['workspace', 'user'], name='unique_workspace_member')]


class Channel(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='channels')
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=240, blank=True)
    kind = models.CharField(max_length=10, choices=[('public', 'Public'), ('private', 'Private'), ('dm', 'Direct message')], default='public')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    dm_key = models.CharField(max_length=80, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['workspace', 'name'], name='unique_channel_name'), models.UniqueConstraint(fields=['workspace', 'dm_key'], name='unique_dm_pair')]

    def __str__(self):
        return f'{self.workspace}: {self.name}'


class ChannelMember(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    last_read_id = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['channel', 'user'], name='unique_channel_member')]


class Message(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField(blank=True, max_length=4000)
    client_message_id = models.UUIDField(default=uuid.uuid4)
    reply_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']
        indexes = [models.Index(fields=['channel', 'id'])]
        constraints = [models.UniqueConstraint(fields=['channel', 'sender', 'client_message_id'], name='unique_client_message')]


class Attachment(models.Model):
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name='attachment')
    file = models.FileField(upload_to='attachments/%Y/%m/')
    name = models.CharField(max_length=200)
    content_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField()


class Invitation(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
