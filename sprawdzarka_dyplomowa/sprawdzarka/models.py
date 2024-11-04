from django.contrib.auth.models import AbstractUser
from django.contrib.auth.hashers import make_password, check_password
from django.db import models

# Extending the User model
class User(AbstractUser):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')


class Contest(models.Model):
    name = models.CharField(max_length=255)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contests')
    start_date = models.DateField()
    end_date = models.DateField()
    send_limit = models.IntegerField()
    password = models.CharField(max_length=128)  # Dodane pole na hasło

    def save(self, *args, **kwargs):
        # Sprawdza, czy hasło nie jest już zaszyfrowane
        if not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)
    
    def check_contest_password(self, raw_password):
        return check_password(raw_password, self.password)


class ContestSigned(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class Lecture(models.Model):
    name = models.CharField(max_length=255)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lectures')
    content_path = models.TextField()


class ContestLecture(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE)


class Task(models.Model):
    name = models.CharField(max_length=255)
    special_id = models.CharField(max_length=100, unique=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    content_path = models.TextField()
    time_limit = models.IntegerField()
    memory_limit = models.IntegerField()


class ContestTask(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)


class TestGroup(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    points = models.IntegerField()


class Test(models.Model):
    name = models.CharField(max_length=255)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='tests')
    group = models.ForeignKey(TestGroup, on_delete=models.CASCADE, related_name='tests')


class Solution(models.Model):
    LANG_CHOICES = [
        ('C/C++', 'C/C++'),
        ('Java', 'Java'),
        ('C#', 'C#'),
    ]
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('testing', 'Testing'),
        ('done', 'Done'),
    ]
    contest_task = models.ForeignKey(ContestTask, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    send_date = models.DateField()
    lang = models.CharField(max_length=10, choices=LANG_CHOICES)
    src_path = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    final_points = models.IntegerField(null=True, blank=True)


class SolutionTestResult(models.Model):
    STATUS_CHOICES = [
        ('OK', 'OK'),
        ('WA', 'Wrong Answer'),
        ('TLE', 'Time Limit Exceeded'),
        ('MLE', 'Memory Limit Exceeded'),
        ('ERR', 'Error'),
    ]
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name='test_results')
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    time = models.IntegerField(null=True, blank=True)
    memory = models.IntegerField(null=True, blank=True)
    passed = models.BooleanField(default=False)
    final_status = models.CharField(max_length=5, choices=STATUS_CHOICES, null=True, blank=True)


class Question(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    date_posted = models.DateField()
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True)
    question = models.TextField()
    answer = models.TextField(null=True, blank=True)
    user_answered = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='answers')


class ForumTopic(models.Model):
    topic = models.CharField(max_length=255)
    date_posted = models.DateField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_topics')


class ForumPost(models.Model):
    topic = models.ForeignKey(ForumTopic, on_delete=models.CASCADE, related_name='posts')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_posts')
    date = models.DateField()
    message = models.TextField()
