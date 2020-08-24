import json
from unittest import mock

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from model_bakery import baker

from newsfeed.models import Issue, Post, Subscriber


class IssueListViewTest(TestCase):

    def setUp(self):
        self.released_issues = baker.make(
            Issue, is_draft=False, _quantity=16,
            publish_date=timezone.now() - timezone.timedelta(days=1)
        )

    def test_issue_list_view_url_exists(self):
        response = self.client.get(reverse('newsfeed:issue_list'))
        self.assertEqual(response.status_code, 200)

    def test_issue_list_view_uses_correct_template(self):
        response = self.client.get(reverse('newsfeed:issue_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'newsfeed/issue_list.html')

    def test_pagination_is_fifteen(self):
        response = self.client.get(reverse('newsfeed:issue_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue('is_paginated' in response.context)
        self.assertTrue(response.context['is_paginated'])
        self.assertTrue(len(response.context['object_list']) == 15)

    def test_issue_list_view_doesnt_show_draft_issues(self):
        Issue.objects.update(is_draft=True)

        response = self.client.get(reverse('newsfeed:issue_list'))
        self.assertEqual(response.status_code, 200)

        self.assertTrue(len(response.context['object_list']) == 0)

    def test_issue_list_view_doesnt_show_future_issues(self):
        Issue.objects.update(
            is_draft=False,
            publish_date=timezone.now() + timezone.timedelta(days=1)
        )

        response = self.client.get(reverse('newsfeed:issue_list'))
        self.assertEqual(response.status_code, 200)

        self.assertTrue(len(response.context['object_list']) == 0)


class IssueDetailViewTest(TestCase):

    def setUp(self):
        self.released_issue = baker.make(
            Issue, is_draft=False,
            publish_date=timezone.now() - timezone.timedelta(days=1)
        )
        self.unreleased_issue = baker.make(Issue, is_draft=True)
        self.posts = baker.make(Post, is_visible=True, _quantity=2)

    def test_issue_detail_view_url_exists(self):
        response = self.client.get(
            reverse(
                'newsfeed:issue_detail',
                kwargs={'issue_number': self.released_issue.issue_number}
            )
        )
        self.assertTrue('issue' in response.context)
        self.assertEqual(response.status_code, 200)

    def test_issue_detail_view_uses_correct_template(self):
        response = self.client.get(
            reverse(
                'newsfeed:issue_detail',
                kwargs={'issue_number': self.released_issue.issue_number}
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'newsfeed/issue_detail.html')

    def test_issue_detail_view_doesnt_show_invisible_posts(self):
        Post.objects.update(is_visible=False)

        response = self.client.get(
            reverse(
                'newsfeed:issue_detail',
                kwargs={'issue_number': self.released_issue.issue_number}
            )
        )
        self.assertEqual(response.status_code, 200)

        self.assertTrue(len(response.context['object_list']) == 0)

    def test_issue_detail_view_not_found_for_draft_issue(self):
        response = self.client.get(
            reverse(
                'newsfeed:issue_detail',
                kwargs={'issue_number': self.unreleased_issue.issue_number}
            )
        )
        self.assertEqual(response.status_code, 404)


class NewsletterSubscribeViewTest(TestCase):

    def setUp(self):
        self.verified_subscriber = baker.make(
            Subscriber, subscribed=True, verified=True
        )

    def test_newsfeed_subscribe_view_url_exists(self):
        response = self.client.get(reverse('newsfeed:newsletter_subscribe'))
        self.assertEqual(response.status_code, 200)

    def test_newsfeed_subscribe_view_uses_correct_template(self):
        response = self.client.get(reverse('newsfeed:newsletter_subscribe'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, 'newsfeed/newsletter_subscribe.html'
        )

    @mock.patch('newsfeed.models.Subscriber.send_verification_email')
    def test_newsfeed_subscribe_view_success(self, send_verification_email):
        response = self.client.post(
            reverse('newsfeed:newsletter_subscribe'),
            data={"email_address": "test@test.com"}
        )

        self.assertRedirects(
            response, reverse('newsfeed:issue_list'),
            status_code=302, target_status_code=200
        )
        message = [
            (m.message, m.level)
            for m in get_messages(response.wsgi_request)
        ][0]

        subscriber = Subscriber.objects.filter(email_address="test@test.com")

        self.assertTrue(subscriber.exists())
        self.assertIn(
            'Thank you for subscribing! '
            'Please check your email inbox to confirm '
            'your subscription to start receiving newsletters.',
            message[0]
        )
        send_verification_email.assert_called_once_with(True)

    @mock.patch('newsfeed.models.Subscriber.send_verification_email')
    def test_newsfeed_subscribe_view_already_subscribed(
        self, send_verification_email
    ):
        response = self.client.post(
            reverse('newsfeed:newsletter_subscribe'),
            data={"email_address": self.verified_subscriber.email_address}
        )

        self.assertRedirects(
            response, reverse('newsfeed:issue_list'),
            status_code=302, target_status_code=200
        )
        message = [
            (m.message, m.level)
            for m in get_messages(response.wsgi_request)
        ][0]

        self.assertIn(
            'You have already subscribed to the newsletter.', message[0]
        )
        send_verification_email.assert_not_called()

    @mock.patch('newsfeed.models.Subscriber.send_verification_email')
    def test_newsfeed_subscribe_view_invalid_email(
        self, send_verification_email
    ):
        response = self.client.post(
            reverse('newsfeed:newsletter_subscribe'),
            data={"email_address": 'invalid_email'}
        )

        self.assertEqual(response.status_code, 200)
        send_verification_email.assert_not_called()

    @mock.patch('newsfeed.models.Subscriber.send_verification_email')
    def test_newsfeed_subscribe_view_success_ajax(
        self, send_verification_email
    ):
        response = self.client.post(
            reverse('newsfeed:newsletter_subscribe'),
            data={"email_address": "test@test.com"},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)

        subscriber = Subscriber.objects.filter(email_address="test@test.com")
        response_data = json.loads(response.content)

        self.assertTrue(subscriber.exists())
        self.assertIn(
            'Thank you for subscribing! '
            'Please check your email inbox to confirm '
            'your subscription to start receiving newsletters.',
            response_data['message']
        )
        self.assertTrue(response_data['success'])
        send_verification_email.assert_called_once_with(True)

    @mock.patch('newsfeed.models.Subscriber.send_verification_email')
    def test_newsfeed_subscribe_view_already_subscribed_ajax(
        self, send_verification_email
    ):
        response = self.client.post(
            reverse('newsfeed:newsletter_subscribe'),
            data={"email_address": self.verified_subscriber.email_address},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)

        response_data = json.loads(response.content)

        self.assertIn(
            'You have already subscribed to the newsletter.',
            response_data['message']
        )
        self.assertFalse(response_data['success'])
        send_verification_email.assert_not_called()

    @mock.patch('newsfeed.models.Subscriber.send_verification_email')
    def test_newsfeed_subscribe_view_invalid_email_ajax(
        self, send_verification_email
    ):
        response = self.client.post(
            reverse('newsfeed:newsletter_subscribe'),
            data={"email_address": 'invalid_email'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 400)

        response_data = json.loads(response.content)

        self.assertEqual(
            {'email_address': ['Enter a valid email address.']},
            response_data
        )
        send_verification_email.assert_not_called()


class NewsletterUnsubscribeViewTest(TestCase):

    def setUp(self):
        self.verified_subscriber = baker.make(
            Subscriber, subscribed=True, verified=True
        )
        self.unsubscribed_email = baker.make(
            Subscriber, subscribed=False, verified=False
        )

    def test_newsfeed_unsubscribe_view_url_exists(self):
        response = self.client.get(reverse('newsfeed:newsletter_unsubscribe'))
        self.assertEqual(response.status_code, 200)

    def test_newsfeed_unsubscribe_view_uses_correct_template(self):
        response = self.client.get(reverse('newsfeed:newsletter_unsubscribe'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, 'newsfeed/newsletter_unsubscribe.html'
        )

    def test_newsfeed_unsubscribe_view_subscriber_does_not_exist(self):
        response = self.client.post(
            reverse('newsfeed:newsletter_unsubscribe'),
            data={"email_address": "test@test.com"}
        )

        self.assertRedirects(
            response, reverse('newsfeed:issue_list'),
            status_code=302, target_status_code=200
        )
        message = [
            (m.message, m.level)
            for m in get_messages(response.wsgi_request)
        ][0]

        subscriber = Subscriber.objects.filter(email_address="test@test.com")

        self.assertFalse(subscriber.exists())
        self.assertIn(
            'Subscriber with this email address does not exist.',
            message[0]
        )

    def test_newsfeed_unsubscribe_view_unsubscribed_email(self):
        response = self.client.post(
            reverse('newsfeed:newsletter_unsubscribe'),
            data={"email_address": self.unsubscribed_email.email_address}
        )

        self.assertRedirects(
            response, reverse('newsfeed:issue_list'),
            status_code=302, target_status_code=200
        )
        message = [
            (m.message, m.level)
            for m in get_messages(response.wsgi_request)
        ][0]

        subscriber = Subscriber.objects.filter(
            subscribed=True,
            email_address=self.unsubscribed_email.email_address
        )

        self.assertFalse(subscriber.exists())
        self.assertIn(
            'Subscriber with this email address does not exist.',
            message[0]
        )

    def test_newsfeed_unsubscribe_view_success(self):
        response = self.client.post(
            reverse('newsfeed:newsletter_unsubscribe'),
            data={"email_address": self.verified_subscriber.email_address}
        )

        self.assertRedirects(
            response, reverse('newsfeed:issue_list'),
            status_code=302, target_status_code=200
        )
        message = [
            (m.message, m.level)
            for m in get_messages(response.wsgi_request)
        ][0]

        self.verified_subscriber.refresh_from_db()
        self.assertFalse(self.verified_subscriber.subscribed)
        self.assertFalse(self.verified_subscriber.verified)

        self.assertIn(
            'You have successfully unsubscribed from the newsletter.',
            message[0]
        )

    def test_newsfeed_unsubscribe_view_invalid_email(self):
        response = self.client.post(
            reverse('newsfeed:newsletter_unsubscribe'),
            data={"email_address": 'invalid_email'}
        )

        self.assertEqual(response.status_code, 200)

    def test_newsfeed_unsubscribe_view_success_ajax(self):
        response = self.client.post(
            reverse('newsfeed:newsletter_unsubscribe'),
            data={"email_address": self.verified_subscriber.email_address},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)

        self.verified_subscriber.refresh_from_db()
        self.assertFalse(self.verified_subscriber.subscribed)
        self.assertFalse(self.verified_subscriber.verified)

        response_data = json.loads(response.content)

        self.assertIn(
            'You have successfully unsubscribed from the newsletter.',
            response_data['message']
        )
        self.assertTrue(response_data['success'])

    def test_newsfeed_unsubscribe_view_subscriber_does_not_exist_ajax(self):
        response = self.client.post(
            reverse('newsfeed:newsletter_unsubscribe'),
            data={"email_address": "test@test.com"},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)

        subscriber = Subscriber.objects.filter(email_address="test@test.com")
        self.assertFalse(subscriber.exists())

        response_data = json.loads(response.content)

        self.assertIn(
            'Subscriber with this email address does not exist.',
            response_data['message']
        )
        self.assertFalse(response_data['success'])

    def test_newsfeed_unsubscribe_view_unsubscribed_email_ajax(self):
        response = self.client.post(
            reverse('newsfeed:newsletter_unsubscribe'),
            data={"email_address": self.unsubscribed_email.email_address},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)

        subscriber = Subscriber.objects.filter(
            subscribed=True,
            email_address=self.unsubscribed_email.email_address
        )

        self.assertFalse(subscriber.exists())

        response_data = json.loads(response.content)

        self.assertIn(
            'Subscriber with this email address does not exist.',
            response_data['message']
        )
        self.assertFalse(response_data['success'])

    def test_newsfeed_unsubscribe_view_invalid_email_ajax(self):
        response = self.client.post(
            reverse('newsfeed:newsletter_unsubscribe'),
            data={"email_address": 'invalid_email'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 400)

        response_data = json.loads(response.content)

        self.assertEqual(
            {'email_address': ['Enter a valid email address.']},
            response_data
        )


class NewsletterSubscriptionConfirmViewTest(TestCase):

    def setUp(self):
        self.verified_subscriber = baker.make(
            Subscriber, subscribed=True, verified=True
        )
        self.unverified_subscriber = baker.make(
            Subscriber, subscribed=False, verified=False,
            verification_sent_date=timezone.now()
        )

    def test_newsfeed_subscribe_view_url_exists(self):
        response = self.client.get(
            reverse(
                'newsfeed:newsletter_subscribe_confirm',
                kwargs={'token': self.unverified_subscriber.token}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue('subscribed' in response.context)
        self.assertTrue(response.context['subscribed'])
        self.assertTemplateUsed(
            response, 'newsfeed/newsletter_subscription_confirm.html'
        )

    def test_newsfeed_subscribe_view_uses_correct_template(self):
        response = self.client.get(
            reverse(
                'newsfeed:newsletter_subscribe_confirm',
                kwargs={'token': self.verified_subscriber.token}
            )
        )
        self.assertEqual(response.status_code, 404)