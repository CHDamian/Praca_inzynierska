from django.contrib import admin
from .models import (
    User, Contest, ContestSigned, Lecture, ContestLecture, Task, 
    ContestTask, TestGroup, Test, Solution, SolutionTestResult, 
    Question, ForumTopic, ForumPost
)

# Register all models with Django admin
admin.site.register(User)
admin.site.register(Contest)
admin.site.register(ContestSigned)
admin.site.register(Lecture)
admin.site.register(ContestLecture)
admin.site.register(Task)
admin.site.register(ContestTask)
admin.site.register(TestGroup)
admin.site.register(Test)
admin.site.register(Solution)
admin.site.register(SolutionTestResult)
admin.site.register(Question)
admin.site.register(ForumTopic)
admin.site.register(ForumPost)
