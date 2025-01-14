from django.contrib.auth.models import AbstractUser
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ValidationError
from django.db import models
from datetime import datetime

class User(AbstractUser):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')

    class Meta:
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"User: {self.first_name} {self.last_name}"


class Contest(models.Model):
    name = models.CharField(max_length=255)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contests')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    send_limit = models.IntegerField(null=True, blank=True)
    password = models.CharField(max_length=128, null=True, blank=True)
    frozen_ranking = models.DateField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.password and not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def check_contest_password(self, raw_password):
        return check_password(raw_password, self.password)

    class Meta:
        verbose_name_plural = 'Contests'

    def __str__(self):
        return f"{self.name} - {self.teacher}"


class ContestSigned(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_selected = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'Contest Signups'

    def __str__(self):
        return f"{self.contest} - {self.user}"


class Lecture(models.Model):
    name = models.CharField(max_length=255)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lectures')
    content_path = models.TextField()
    is_public = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'Lectures'

    def __str__(self):
        return f"{self.name}"


class ContestLecture(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = 'Contest Lectures'

    def __str__(self):
        return f"{self.contest} - {self.lecture}"


class Task(models.Model):
    name = models.CharField(max_length=255)
    special_id = models.CharField(max_length=100, unique=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    content_path = models.TextField()
    pdf_file = models.TextField()
    time_limit = models.IntegerField()
    memory_limit = models.IntegerField()
    is_public = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'Tasks'

    def __str__(self):
        return f"{self.special_id} - {self.name}"


class ContestTask(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = 'Contest Tasks'

    def __str__(self):
        return f"{self.contest} - {self.task}"


class TestGroup(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    points = models.IntegerField()

    class Meta:
        verbose_name_plural = 'Test Groups'

    def __str__(self):
        return f"{self.task} - {self.name}"
    
    def clean(self):
        total_points = sum(group.points for group in TestGroup.objects.filter(task=self.task))
        if total_points > 100:
            raise ValidationError('Suma punktów dla wszystkich grup nie może przekraczać 100.')


class Test(models.Model):
    name = models.CharField(max_length=255)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='tests')
    group = models.ForeignKey(TestGroup, on_delete=models.SET_NULL, related_name='tests', null=True, blank=True)
    in_file = models.TextField()
    out_file = models.TextField()

    class Meta:
        verbose_name_plural = 'Tests'

    def __str__(self):
        return f"{self.task} - {self.name}"


class Solution(models.Model):
    LANG_CHOICES = [('C/C++', 'C/C++'), ('Java', 'Java'), ('C#', 'C#')]
    STATUS_CHOICES = [('waiting', 'Waiting'), ('testing', 'Testing'), ('done', 'Done'), ('error', 'Error')]
    contest_task = models.ForeignKey(ContestTask, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    send_date = models.DateTimeField()
    lang = models.CharField(max_length=10, choices=LANG_CHOICES)
    src_path = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    final_points = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name_plural = 'Solutions'

    def __str__(self):
        send_date_str = self.send_date.strftime('%Y.%m.%d::%H:%M:%S')
        return f"{self.contest_task}, {self.author}, {send_date_str}"


class SolutionTestResult(models.Model):
    STATUS_CHOICES = [
        ('OK', 'OK'),
        ('WA', 'Wrong Answer'),
        ('TLE', 'Time Limit Exceeded'),
        ('MLE', 'Memory Limit Exceeded'),
        ('ERR', 'Error')
    ]
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name='test_results')
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    time = models.IntegerField(null=True, blank=True)
    memory = models.IntegerField(null=True, blank=True)
    passed = models.BooleanField(default=False)
    final_status = models.CharField(max_length=5, choices=STATUS_CHOICES, null=True, blank=True)

    class Meta:
        verbose_name_plural = 'Solution Test Results'

    def __str__(self):
        return f"{self.solution} - {self.test}"


class Question(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    date_posted = models.DateTimeField()
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=128, null=True, blank=True)
    question = models.TextField()
    answer = models.TextField(null=True, blank=True)
    user_answered = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='answers')

    class Meta:
        verbose_name_plural = 'Questions'

    def __str__(self):
        date_str = self.date_posted.strftime('%Y.%m.%d::%H:%M:%S')
        return f"{self.contest}, {self.user}, {date_str}"


class ForumTopic(models.Model):
    topic = models.CharField(max_length=255)
    date_posted = models.DateTimeField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_topics')

    class Meta:
        verbose_name_plural = 'Forum Topics'

    def __str__(self):
        date_str = self.date_posted.strftime('%Y.%m.%d::%H:%M:%S')
        return f"{self.topic}, {date_str}"


class ForumPost(models.Model):
    topic = models.ForeignKey(ForumTopic, on_delete=models.CASCADE, related_name='posts')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_posts')
    date = models.DateTimeField()
    message = models.TextField()

    class Meta:
        verbose_name_plural = 'Forum Posts'

    def __str__(self):
        date_str = self.date.strftime('%Y.%m.%d::%H:%M:%S')
        return f"{self.topic} - {self.user}, {date_str}"
