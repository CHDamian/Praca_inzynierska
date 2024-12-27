from celery import shared_task

@shared_task
def execute_cpp(solution_id):
    print(f"Executing C++ for solution ID: {solution_id}...")

@shared_task
def execute_java(solution_id):
    print(f"Executing Java for solution ID: {solution_id}...")

@shared_task
def execute_cs(solution_id):
    print(f"Executing C# for solution ID: {solution_id}...")
