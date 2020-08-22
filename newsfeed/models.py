import uuid

from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.urls import reverse
from django.utils import timezone

from .constants import ISSUE_TYPE_CHOICES, WEEKLY_ISSUE
from .querysets import IssueQuerySet, SubscriberQuerySet, PostQuerySet
from .utils.send_verification import send_subscription_verification_email


class Issue(models.Model):
    title = models.CharField(max_length=128)
    issue_number = models.PositiveIntegerField(
        unique=True, help_text='Used as a slug for each issue'
    )
    publish_date = models.DateTimeField()
    issue_type = models.PositiveSmallIntegerField(
        choices=ISSUE_TYPE_CHOICES,
        default=WEEKLY_ISSUE
    )
    short_description = models.TextField(blank=True, null=True)
    is_draft = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = IssueQuerySet.as_manager()

    class Meta:
        ordering = ['-publish_date', '-issue_number']

    def __str__(self):
        return self.title

    def is_published(self):
        return self.is_draft == False and self.publish_date <= timezone.now()

    def get_absolute_url(self):
        return reverse(
            'newsfeed:issue_detail',
            kwargs={'issue_number': self.issue_number}
        )


class PostCategory(models.Model):
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = 'Post categories'
        ordering = ['order']

    def __str__(self):
        return self.name


class Post(models.Model):
    issue = models.ForeignKey(
        Issue,
        on_delete=models.SET_NULL,
        related_name='posts',
        blank=True,
        null=True
    )
    category = models.ForeignKey(
        PostCategory,
        on_delete=models.SET_NULL,
        related_name='posts',
        blank=True,
        null=True
    )
    title = models.CharField(max_length=255)
    source_url = models.URLField()
    is_visible = models.BooleanField(default=False)
    short_description = models.TextField()
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title


class Newsletter(models.Model):
    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name='newsletters'
    )
    subject = models.CharField(max_length=128)
    schedule = models.DateTimeField(blank=True, null=True)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.subject


class Subscriber(models.Model):
    email_address = models.EmailField(unique=True)
    token = models.CharField(max_length=128, unique=True, default=uuid.uuid4)
    verified = models.BooleanField(default=False)
    subscribed = models.BooleanField(default=False)
    verification_sent_date = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = SubscriberQuerySet.as_manager()

    def __str__(self):
        return self.email_address

    def token_expired(self):
        if not self.verification_sent_date:
            return True

        expiration_date = (
            self.verification_sent_date +
            timezone.timedelta(
                days=settings.SUBSCRIPTION_EMAIL_CONFIRMATION_EXPIRE_DAYS
            )
        )
        return expiration_date <= timezone.now()

    def reset_token(self):
        unique_token = str(uuid.uuid4())

        while self.__class__.objects.filter(token=unique_token).exists():
            unique_token = str(uuid.uuid4())

        self.token = unique_token
        self.save()

    def verify(self):
        if not self.token_expired():
            self.verified = True
            self.subscribed = True
            self.save()

            return True

    def unsubscribe(self):
        if self.subscribed:
            self.subscribed = False
            self.verified = False
            self.save()

            return True

    def send_verification_email(self, created):
        minutes_before = timezone.now() - timezone.timedelta(minutes=5)

        if (
            self.verification_sent_date and
            self.verification_sent_date >= minutes_before
        ):
            return

        if not created:
            self.reset_token()

        self.verification_sent_date = timezone.now()
        self.save()

        send_subscription_verification_email(
            self.get_verification_url(), self.email_address
        )

    def get_verification_url(self):
        return reverse(
            'newsfeed:newsletter_subscribe_confirm',
            kwargs={'token': self.token}
        )
