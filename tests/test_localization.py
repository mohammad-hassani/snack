import json
import uuid
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from chat.models import Channel, Membership, Workspace


class PersianInterfaceTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_auth_pages_use_persian_and_rtl(self):
        for path in ['/accounts/login/', '/accounts/signup/', '/accounts/password_reset/']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertContains(response, 'lang="fa" dir="rtl"')
                self.assertContains(response, 'تیم‌فلو')
                self.assertNotContains(response, '>Sign in<')
                self.assertNotContains(response, '>Password:')
        login = self.client.get('/accounts/login/')
        self.assertContains(login, 'dir="ltr"')
        invalid = self.client.post('/accounts/login/', {'username': 'invalid', 'password': 'bad'})
        self.assertNotContains(invalid, 'Enter a valid email address.')
        self.assertTrue(invalid.context['form'].errors)

    def test_chat_errors_and_persian_content(self):
        user = User.objects.create_user('farsi@example.com', 'farsi@example.com', 'local-test-password', first_name='مینا')
        workspace = Workspace.objects.create(name='تیم طراحی', slug='farsi')
        Membership.objects.create(user=user, workspace=workspace, role='admin')
        channel = Channel.objects.create(workspace=workspace, name='گفتگوی عمومی', created_by=user)
        self.client.force_login(user)
        response = self.client.get('/')
        self.assertContains(response, 'lang="fa" dir="rtl"')
        self.assertContains(response, 'جستجو در فضای کاری')
        self.assertContains(response, 'مدیریت اعضا')
        url = f'/api/channels/{channel.pk}/messages/'
        body = 'سلام تیم! بررسی API v2 در ساعت ۱۲:۳۰'
        payload = {'body': body, 'client_message_id': str(uuid.uuid4())}
        self.assertEqual(self.client.post(url, json.dumps(payload), content_type='application/json').json()['message']['body'], body)
        payload['body'] = ''
        error = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(error.status_code, 400)
        self.assertIn('پیامی', error.json()['error'])
        history = self.client.get(url).json()['messages']
        self.assertEqual(history[0]['body'], body)
        self.assertEqual(history[0]['sender'], 'مینا')
