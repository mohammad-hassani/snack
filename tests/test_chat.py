import json
import tempfile
import uuid
from datetime import timedelta
from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from chat.models import Channel, ChannelMember, Invitation, Membership, Message, Workspace
from chat.services import send_message
from teamflow.asgi import application


class ChatTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('admin@test.com', 'admin@test.com', 'complex-test-password', first_name='Mina')
        cls.member = User.objects.create_user('member@test.com', 'member@test.com', 'complex-test-password', first_name='Omid')
        cls.outsider = User.objects.create_user('outside@test.com', 'outside@test.com', 'complex-test-password')
        cls.workspace = Workspace.objects.create(name='Studio', slug='studio')
        Membership.objects.create(workspace=cls.workspace, user=cls.admin, role='admin')
        Membership.objects.create(workspace=cls.workspace, user=cls.member)
        cls.public = Channel.objects.create(workspace=cls.workspace, name='general', created_by=cls.admin)
        cls.private = Channel.objects.create(workspace=cls.workspace, name='leadership', kind='private', created_by=cls.admin)
        ChannelMember.objects.create(channel=cls.private, user=cls.admin)

    def setUp(self):
        cache.clear()
        self.client.force_login(self.admin)

    def post_json(self, url, data):
        return self.client.post(url, json.dumps(data), content_type='application/json')

    def send(self, channel=None, body='Hello', client_id=None):
        return self.post_json(f'/api/channels/{(channel or self.public).pk}/messages/', {'body': body, 'client_message_id': str(client_id or uuid.uuid4())})

    def test_idempotency_and_refresh(self):
        token = uuid.uuid4()
        self.assertEqual(self.send(client_id=token).status_code, 201)
        self.assertEqual(self.send(client_id=token).status_code, 201)
        self.assertEqual(Message.objects.count(), 1)
        history = self.client.get(f'/api/channels/{self.public.pk}/messages/').json()
        self.assertEqual(history['messages'][0]['body'], 'Hello')

    def test_private_and_workspace_isolation(self):
        secret = send_message(self.admin, self.private.pk, 'Secret', uuid.uuid4())
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(f'/api/channels/{self.private.pk}/messages/').status_code, 403)
        self.assertEqual(self.send(channel=self.private).status_code, 403)
        bootstrap = self.client.get(f'/api/workspaces/{self.workspace.pk}/').json()
        self.assertNotIn(self.private.pk, [channel['id'] for channel in bootstrap['channels']])
        self.assertEqual(self.client.get(f'/api/workspaces/{self.workspace.pk}/search/?q=Secret').json()['messages'], [])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(f'/api/channels/{self.public.pk}/messages/').status_code, 403)
        self.assertEqual(self.client.get(f'/api/workspaces/{self.workspace.pk}/').status_code, 403)
        self.assertIsNotNone(secret.pk)

    def test_edit_delete_and_reply_permissions(self):
        message = self.send().json()['message']
        self.client.force_login(self.member)
        url = f'/api/messages/{message["id"]}/'
        self.assertEqual(self.client.patch(url, json.dumps({'body': 'Changed'}), content_type='application/json').status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        foreign = send_message(self.admin, self.private.pk, 'secret', uuid.uuid4())
        self.assertEqual(self.post_json(f'/api/channels/{self.public.pk}/messages/', {'body': 'reply', 'client_message_id': str(uuid.uuid4()), 'reply_to': foreign.pk}).status_code, 400)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.patch(url, json.dumps({'body': 'Changed'}), content_type='application/json').json()['message']['body'], 'Changed')
        self.assertTrue(self.client.delete(url).json()['message']['deleted'])
        self.assertEqual(Message.objects.get(pk=message['id']).body, '')

    def test_cursor_history_and_recovery(self):
        Message.objects.bulk_create([Message(channel=self.public, sender=self.admin, body=f'message {i}') for i in range(65)])
        url = f'/api/channels/{self.public.pk}/messages/'
        latest = self.client.get(url).json()
        self.assertEqual(len(latest['messages']), 50)
        self.assertTrue(latest['has_more'])
        older = self.client.get(url, {'before': latest['messages'][0]['id']}).json()
        self.assertEqual(len(older['messages']), 15)
        recovered = self.client.get(url, {'after': older['messages'][-1]['id']}).json()
        self.assertEqual(recovered['messages'], latest['messages'])

    def test_unread_monotonic_read_cursor(self):
        first = self.send().json()['message']['id']
        second = self.send().json()['message']['id']
        self.client.force_login(self.member)
        url = f'/api/workspaces/{self.workspace.pk}/'
        self.assertEqual(self.client.get(url).json()['channels'][0]['unread'], 2)
        read = f'/api/channels/{self.public.pk}/read/'
        self.post_json(read, {'message_id': second})
        self.post_json(read, {'message_id': first})
        self.assertEqual(ChannelMember.objects.get(channel=self.public, user=self.member).last_read_id, second)
        self.assertEqual(self.client.get(url).json()['channels'][0]['unread'], 0)

    def test_direct_messages_are_unique_and_private(self):
        url = f'/api/workspaces/{self.workspace.pk}/direct/'
        result = self.post_json(url, {'user_id': self.member.pk}).json()
        self.client.force_login(self.member)
        self.assertEqual(self.post_json(url, {'user_id': self.admin.pk}).json()['id'], result['id'])
        channel = Channel.objects.get(pk=result['id'])
        self.assertEqual(channel.members.count(), 2)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(f'/api/channels/{channel.pk}/messages/').status_code, 403)

    def test_upload_validation_and_protected_download(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            url = f'/api/channels/{self.private.pk}/messages/'
            response = self.client.post(url, {'body': '', 'client_message_id': str(uuid.uuid4()), 'file': SimpleUploadedFile('notes.txt', b'private notes', content_type='text/plain')})
            self.assertEqual(response.status_code, 201)
            file_url = response.json()['message']['attachment']['url']
            download = self.client.get(file_url)
            self.assertEqual(b''.join(download.streaming_content), b'private notes')
            self.client.force_login(self.member)
            self.assertEqual(self.client.get(file_url).status_code, 403)
            self.client.force_login(self.admin)
            invalid = self.client.post(url, {'body': '', 'client_message_id': str(uuid.uuid4()), 'file': SimpleUploadedFile('image.png', b'not an image')})
            self.assertEqual(invalid.status_code, 400)
            invalid = self.client.post(url, {'body': '', 'client_message_id': str(uuid.uuid4()), 'file': SimpleUploadedFile('run.exe', b'code')})
            self.assertEqual(invalid.status_code, 400)
            self.client.delete(f'/api/messages/{response.json()["message"]["id"]}/')
            self.assertEqual(self.client.get(file_url).status_code, 404)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_invitation_email_identity_expiry_and_replay(self):
        response = self.post_json(f'/api/workspaces/{self.workspace.pk}/invites/', {'email': self.outsider.email})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        invitation = Invitation.objects.get()
        url = f'/invite/{invitation.token}/'
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertTrue(Membership.objects.filter(workspace=self.workspace, user=self.outsider).exists())
        self.assertEqual(self.client.post(url).status_code, 400)
        invitation.accepted_at = None
        invitation.created_at = timezone.now() - timedelta(days=8)
        invitation.save()
        self.assertEqual(self.client.post(url).status_code, 400)

    def test_admin_guard_and_member_removal(self):
        url = f'/api/workspaces/{self.workspace.pk}/members/{self.admin.pk}/'
        self.assertEqual(self.post_json(url, {'role': 'remove'}).status_code, 400)
        self.client.force_login(self.member)
        self.assertEqual(self.post_json(url, {'role': 'admin'}).status_code, 404)
        self.client.force_login(self.admin)
        url = f'/api/workspaces/{self.workspace.pk}/members/{self.member.pk}/'
        self.assertEqual(self.post_json(url, {'role': 'remove'}).status_code, 200)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(f'/api/channels/{self.public.pk}/messages/').status_code, 403)

    def test_validation_and_csrf(self):
        self.assertEqual(self.send(body='').status_code, 400)
        self.assertEqual(self.send(body='a' * 4001).status_code, 400)
        self.assertEqual(self.post_json(f'/api/channels/{self.public.pk}/messages/', {'body': 'Hi', 'client_message_id': 'invalid'}).status_code, 400)
        self.assertEqual(self.post_json(f'/api/workspaces/{self.workspace.pk}/channels/', {'name': 123}).status_code, 400)
        self.assertEqual(self.post_json(f'/api/workspaces/{self.workspace.pk}/channels/', []).status_code, 400)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(f'/api/channels/{self.public.pk}/messages/', {}).status_code, 403)

    def test_signup_workspace_login_and_password_reset_pages(self):
        self.client.logout()
        response = self.client.post('/accounts/signup/', {'email': 'new@test.com', 'first_name': 'New', 'password1': 'A-long-enough-password-123', 'password2': 'A-long-enough-password-123'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.get(email='new@test.com').username, 'new@test.com')
        self.assertEqual(self.client.post('/workspaces/create/', {'name': 'Fresh team'}).status_code, 302)
        self.client.logout()
        self.assertTrue(self.client.login(username='new@test.com', password='A-long-enough-password-123'))
        self.client.logout()
        self.assertEqual(self.client.post('/accounts/login/', {'username': 'NEW@TEST.COM', 'password': 'A-long-enough-password-123'}).status_code, 302)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.client.logout()
        for path in ['/accounts/login/', '/accounts/password_reset/']:
            self.assertEqual(self.client.get(path).status_code, 200)


class WebsocketTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('socket@test.com', 'socket@test.com', 'socket-test-password')
        self.workspace = Workspace.objects.create(name='Sockets', slug='sockets')
        Membership.objects.create(workspace=self.workspace, user=self.user, role='admin')
        self.channel = Channel.objects.create(workspace=self.workspace, name='general', created_by=self.user)
        self.client.force_login(self.user)
        self.cookie = f'sessionid={self.client.cookies["sessionid"].value}'.encode()

    def communicator(self, authenticated=True, origin=b'http://testserver'):
        headers = [(b'origin', origin)]
        if authenticated:
            headers.append((b'cookie', self.cookie))
        return WebsocketCommunicator(application, f'/ws/workspaces/{self.workspace.pk}/', headers=headers)

    def test_authentication_origin_and_expired_session(self):
        async def scenario():
            anonymous = self.communicator(False)
            self.assertFalse((await anonymous.connect())[0])
            await anonymous.disconnect()
            bad_origin = self.communicator(origin=b'https://attacker.example')
            self.assertFalse((await bad_origin.connect())[0])
            await bad_origin.disconnect()
            socket = self.communicator()
            self.assertTrue((await socket.connect())[0])
            self.assertEqual((await socket.receive_json_from())['event'], 'ready')
            await sync_to_async(self.client.logout)()
            await socket.send_json_to({'event': 'ping'})
            self.assertEqual((await socket.receive_output())['code'], 4401)
            await socket.disconnect()
        async_to_sync(scenario)()

    def test_persist_broadcast_ack_dedupe_and_typing(self):
        async def scenario():
            socket = self.communicator()
            self.assertTrue((await socket.connect())[0])
            await socket.receive_json_from()
            token = str(uuid.uuid4())
            await socket.send_json_to({'event': 'send:message', 'channel_id': self.channel.pk, 'body': 'Live hello', 'client_message_id': token})
            events = [await socket.receive_json_from(), await socket.receive_json_from()]
            self.assertEqual({event['event'] for event in events}, {'new:message', 'ack:message'})
            self.assertEqual(await sync_to_async(Message.objects.count)(), 1)
            await socket.send_json_to({'event': 'send:message', 'channel_id': self.channel.pk, 'body': 'Live hello', 'client_message_id': token})
            self.assertEqual((await socket.receive_json_from())['event'], 'ack:message')
            self.assertEqual(await sync_to_async(Message.objects.count)(), 1)
            await socket.send_json_to({'event': 'start:typing', 'channel_id': self.channel.pk})
            self.assertEqual((await socket.receive_json_from())['event'], 'start:typing')
            await socket.disconnect()
        async_to_sync(scenario)()

    def test_removed_member_stops_receiving_events(self):
        async def scenario():
            socket = self.communicator()
            self.assertTrue((await socket.connect())[0])
            await socket.receive_json_from()
            await sync_to_async(Membership.objects.filter(user=self.user).delete)()
            await socket.send_json_to({'event': 'send:message', 'channel_id': self.channel.pk, 'body': 'No access', 'client_message_id': str(uuid.uuid4())})
            self.assertEqual((await socket.receive_json_from())['event'], 'error')
            self.assertEqual(await sync_to_async(Message.objects.count)(), 0)
            await socket.disconnect()
        async_to_sync(scenario)()

    def test_ten_connections_twenty_sends_fanout_and_latency(self):
        import time
        async def scenario():
            sockets = [self.communicator() for _ in range(10)]
            for socket in sockets:
                self.assertTrue((await socket.connect())[0])
                await socket.receive_json_from()
            samples = []
            for index in range(20):
                started = time.perf_counter()
                await sockets[0].send_json_to({'event': 'send:message', 'channel_id': self.channel.pk, 'body': f'Load smoke {index}', 'client_message_id': str(uuid.uuid4())})
                sender_events = [await sockets[0].receive_json_from(), await sockets[0].receive_json_from()]
                self.assertEqual({event['event'] for event in sender_events}, {'new:message', 'ack:message'})
                for socket in sockets[1:]:
                    self.assertEqual((await socket.receive_json_from())['event'], 'new:message')
                samples.append((time.perf_counter() - started) * 1000)
            self.assertEqual(await sync_to_async(Message.objects.count)(), 20)
            for socket in sockets:
                await socket.disconnect()
            p95 = sorted(samples)[18]
            print(f'\nASGI load smoke: 10 connections, 20 sends, 200 deliveries, p95={p95:.1f}ms (in-process, not a network benchmark).')
        async_to_sync(scenario)()
