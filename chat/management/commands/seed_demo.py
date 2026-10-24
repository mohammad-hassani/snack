import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from chat.models import Channel, ChannelMember, Membership, Message, Workspace


class Command(BaseCommand):
    help = 'Create a local demo workspace. Disabled when DEBUG=0.'

    def add_arguments(self, parser):
        parser.add_argument('--password', help='Demo login password; generated when omitted.')

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo data is only available in development.')
        if Workspace.objects.filter(slug='acme-studio-demo').exists():
            self.stdout.write('Demo workspace already exists. Existing passwords were not changed.')
            return
        password = options['password'] or secrets.token_urlsafe(18)
        people = [('Mina Farhadi', 'mina'), ('Omid Rahimi', 'omid'), ('Sara Ahmadi', 'sara'), ('Daniel Park', 'daniel'), ('Nika Moradi', 'nika')]
        users = []
        for name, handle in people:
            email = f'{handle}@teamflow.local'
            if User.objects.filter(username=email).exists():
                raise CommandError(f'{email} already exists. No demo accounts were changed.')
            users.append(User.objects.create_user(username=email, email=email, first_name=name, password=password))
        workspace = Workspace.objects.create(name='Acme Studio', slug='acme-studio-demo')
        for index, user in enumerate(users):
            Membership.objects.create(workspace=workspace, user=user, role='admin' if index == 0 else 'member')
        channels = {}
        for name, description in [('general', 'The little things, the big updates, and everything that brings us together.'), ('design', 'Ideas in progress. Thoughtful feedback. Better experiences.'), ('engineering', 'Build, share, and help each other get unstuck.'), ('random', 'A little room for everything else.'), ('announcements', 'The updates everyone should know about.')]:
            channel = Channel.objects.create(workspace=workspace, name=name, description=description, created_by=users[0])
            channels[name] = channel
            for user in users:
                ChannelMember.objects.create(channel=channel, user=user)
        content = [
            (0, 'Morning, team! ☀️\nA fresh week and some good things ahead. How’s everyone doing?'),
            (1, 'Morning! Coffee is ready and the new onboarding flow is looking really good. Excited to share it today.'),
            (2, 'Happy Monday! Just added the latest explorations to #design. Would love a fresh pair of eyes when you have a moment. ✨'),
            (3, 'The API updates are ready for review. A few small improvements that should make everything feel a little faster. 🚀'),
            (0, 'Love the progress. Let’s keep the feedback coming here — no need to wait for a meeting. 🙌'),
            (4, 'Small win: our first customer interview is booked for Thursday! I’ll share the notes with everyone afterwards. 🎉'),
        ]
        for index, (sender, body) in enumerate(content):
            message = Message.objects.create(channel=channels['general'], sender=users[sender], body=body)
            Message.objects.filter(pk=message.pk).update(created_at=timezone.now() - timedelta(minutes=45 - index * 5))
        for channel_name, body in [('design', 'A home for work in progress. Share early, ask questions, and make it better together. ✨'), ('engineering', 'What are you working on this week? Drop your updates here.'), ('announcements', 'Welcome to our shared workspace! Start with #general and make yourself at home. 👋')]:
            Message.objects.create(channel=channels[channel_name], sender=users[0], body=body)
        direct = Channel.objects.create(workspace=workspace, name=f'dm-{users[0].pk}:{users[1].pk}', kind='dm', dm_key=f'{users[0].pk}:{users[1].pk}', created_by=users[0])
        for user in users[:2]:
            ChannelMember.objects.create(channel=direct, user=user)
        Message.objects.create(channel=direct, sender=users[1], body='Hey Mina! Have a moment to chat about the onboarding flow?')
        self.stdout.write(self.style.SUCCESS(f'Demo ready. Email: mina@teamflow.local\nPassword: {password}'))
