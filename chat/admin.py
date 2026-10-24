from django.contrib import admin
from .models import Workspace, Membership, Channel, ChannelMember, Message, Attachment, Invitation

for model in (Workspace, Membership, Channel, ChannelMember, Message, Attachment, Invitation):
    admin.site.register(model)
admin.site.site_header = 'مدیریت تیم‌فلو'

admin.site.site_title = 'تیم‌فلو'
admin.site.index_title = 'مدیریت فضای کاری'
