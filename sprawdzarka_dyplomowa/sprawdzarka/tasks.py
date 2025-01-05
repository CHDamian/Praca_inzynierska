import os
import shutil
import platform
import subprocess
from celery import shared_task
from django.db import transaction
from .models import Solution, Test, TestGroup, SolutionTestResult
from django.utils.timezone import now  # Używane do łapania aktualnego czasu, jeśli kiedyś chcemy mierzyć czas testów.

def windows_to_linux_path(path):
    """Konwertuje ścieżkę Windows na format Linuksa."""
    if platform.system() == "Windows":
        return path.replace("\\", "/").replace("C:", "/mnt/c")
    return path

@shared_task
def execute_cpp(solution_id):
    print(f"Executing C++ for solution ID: {solution_id}...")
    
    # 1. Getting solution info...
    print("Getting solution info...")
    try:
        with transaction.atomic():
            solution = Solution.objects.select_related('contest_task__task', 'author').get(id=solution_id)
            print(f"Solution retrieved: {solution}")
            task = solution.contest_task.task
            src_path = os.path.join("media", "solutions", solution.src_path)
            folder_path, file_name = os.path.split(src_path)
            compiled_file_name = os.path.splitext(file_name)[0]
            compiled_file_path = os.path.join(folder_path, compiled_file_name)
            task_folder = task.pdf_file.split("\\")[1]  # Pobranie folderu zadania z pdf_file
            test_folder = os.path.join("media", "tasks", task_folder, "tests")
    except Solution.DoesNotExist:
        print(f"Solution with ID {solution_id} does not exist.")
        return
    except Exception as e:
        print(f"An error occurred while retrieving the solution: {e}")
        return
    
    # 2. Getting grouped tests...
    print("Getting grouped tests...")
    try:
        with transaction.atomic():
            test_groups = TestGroup.objects.filter(task=task)
            grouped_tests = {
                group.name: list(group.tests.all())
                for group in test_groups
            }
            ungrouped_tests = list(Test.objects.filter(task=task, group__isnull=True))
    except Exception as e:
        print(f"An error occurred while retrieving tests: {e}")
        return
    
    # 3. Compile program...
    print("Compile program...")
    try:
        docker_command = [
            "docker", "run", "--rm",
            "-v", f"{os.path.abspath(folder_path)}:/app",  # Montujemy katalog folder_path do /app
            "-w", "/app",  # Pracujemy w katalogu /app w kontenerze
            "gcc:9",  # Używamy obrazu gcc w wersji 9
            "g++", file_name, "-o", compiled_file_name  # Kompilujemy file_name do compiled_file_name
        ]

        result = subprocess.run(
            docker_command,
            timeout=10,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True
        )

        # Logowanie wyjścia kompilacji
        print(f"Compilation stdout:\n{result.stdout}")
        print(f"Compilation stderr:\n{result.stderr}")

        if result.returncode != 0:
            print("Compilation failed:")
            print(result.stderr)
            # Sprzątanie w przypadku błędu kompilacji
            try:
                compiled_file_path = os.path.join(folder_path, compiled_file_name)
                if os.path.exists(compiled_file_path):
                    os.remove(compiled_file_path)
            except Exception as cleanup_error:
                print(f"Error during cleanup: {cleanup_error}")
            return
        else:
            print("Compilation succeeded.")
            compiled_file_path = os.path.join(folder_path, compiled_file_name)
            print(f"Compiled file path: {compiled_file_path}")
    except subprocess.TimeoutExpired:
        print("Compilation timed out.")
        # Sprzątanie w przypadku timeoutu
        try:
            compiled_file_path = os.path.join(folder_path, compiled_file_name)
            if os.path.exists(compiled_file_path):
                os.remove(compiled_file_path)
        except Exception as cleanup_error:
            print(f"Error during cleanup: {cleanup_error}")
        return
    except Exception as e:
        print(f"An unexpected error occurred during compilation: {e}")
        return


    # 4. Testing program...
    print("Testing program...")
    total_points = 0
    group_total_points = sum(group.points for group in test_groups)
    group_points = 0
    ungrouped_points = 0
    ungrouped_tests_passed = 0
    ungrouped_num = len(ungrouped_tests)


    def execute_test(input_file, expected_output_file, test, solution, time_limit, memory_limit):
        try:
            # Kopiowanie plików do katalogu rozwiązania
            copied_input = os.path.join(folder_path, os.path.basename(input_file))
            copied_expected = os.path.join(folder_path, os.path.basename(expected_output_file))
            shutil.copy(input_file, copied_input)
            shutil.copy(expected_output_file, copied_expected)

            # Uruchomienie programu
            with open(copied_input, 'r') as input_file_handle:
                docker_command = (
                    f"docker run --rm -i "
                    f"-v {os.path.abspath(folder_path)}:/app "
                    f"-w /app "
                    f"--pids-limit=1 "
                    f"--memory={memory_limit}m --memory-swap={memory_limit}m "
                    f"gcc:9 "
                    f"bash -c ./{compiled_file_name}"
                )
                print(f"Executing Docker command: {docker_command}")
                
                result = subprocess.run(
                    docker_command,
                    shell=True,
                    stdin=input_file_handle,
                    capture_output=True,
                    timeout=time_limit,
                    text=True
                )

            # Weryfikacja kodu wyjścia
            if result.returncode != 0:
                status = 'ERR'
                passed = False
            else:
                program_output = result.stdout.strip().split()
                with open(copied_expected, 'r') as expected_out:
                    expected_output = expected_out.read().strip().split()
                if program_output == expected_output:
                    status = 'OK'
                    passed = True
                else:
                    status = 'WA'
                    passed = False

            # Tworzenie rekordu w bazie danych
            SolutionTestResult.objects.create(
                solution=solution,
                test=test,
                passed=passed,
                final_status=status,
                time=None,  # W przyszłości zmierzymy czas wykonania
                memory=None  # W przyszłości zmierzymy zużycie pamięci
            )

            return "OK" if passed else status
        except subprocess.TimeoutExpired:
            SolutionTestResult.objects.create(
                solution=solution,
                test=test,
                passed=False,
                final_status='TLE',
                time=None,
                memory=None
            )
            return "Przekroczenie limitu czasu"
        except MemoryError:
            SolutionTestResult.objects.create(
                solution=solution,
                test=test,
                passed=False,
                final_status='MLE',
                time=None,
                memory=None
            )
            return "Przekroczenie limitu pamięci"
        except Exception as e:
            SolutionTestResult.objects.create(
                solution=solution,
                test=test,
                passed=False,
                final_status='ERR',
                time=None,
                memory=None
            )
            return f"Błąd: {e}"
        finally:
            # Usuwanie plików testowych
            try:
                if os.path.exists(copied_input):
                    os.remove(copied_input)
                if os.path.exists(copied_expected):
                    os.remove(copied_expected)
            except Exception as cleanup_error:
                print(f"Error during cleanup: {cleanup_error}")


    # Testowanie grup
    for group_name, tests in grouped_tests.items():
        print(f"Testing group: {group_name}")
        group_success = True
        for test in tests:
            test_input = os.path.join(test_folder, test.name, test.in_file)
            test_expected = os.path.join(test_folder, test.name, test.out_file)
            print(f"Running test: {test.name}")
            result = execute_test(test_input, test_expected, test, solution, task.time_limit, task.memory_limit)
            print(f"Result for {test.name}: {result}")
            if result != "OK":
                print(f"Group {group_name} failed due to: {result}")
                group_success = False
                break
        if group_success:
            group_points += next(group.points for group in test_groups if group.name == group_name)

    # Testowanie niepogrupowanych testów
    print("Testing ungrouped tests:")
    for test in ungrouped_tests:
        test_input = os.path.join(test_folder, test.name, test.in_file)
        test_expected = os.path.join(test_folder, test.name, test.out_file)
        print(f"Running test: {test.name}")
        result = execute_test(test_input, test_expected, test, solution, task.time_limit, task.memory_limit)
        print(f"Result for {test.name}: {result}")
        if result == "OK":
            ungrouped_tests_passed += 1


    if ungrouped_num > 0:
        ungrouped_points = ungrouped_tests_passed * (100 - group_total_points) // ungrouped_num
    else:
        ungrouped_points = 100 - group_total_points

    # Obliczanie wyników
    total_points = group_points + ungrouped_points
    print(f"Total points: {total_points} / 100")

    # 5. Grading…
    print("Grading…")
    solution.final_points = total_points
    solution.status = "done"
    solution.save()
    
    # 6. DONE!
    print("DONE!")



@shared_task
def execute_java(solution_id):
    print(f"Executing Java for solution ID: {solution_id}...")
    
    # 1. Getting solution info...
    print("Getting solution info...")
    # Miejsce na getting solution info...
    
    # 2. Getting grouped tests...
    print("Getting grouped tests...")
    # Miejsce na getting grouped tests...
    
    # 3. Compile program...
    print("Compile program...")
    # Miejsce na compile program...
    
    # 4. Testing program...
    print("Testing program...")
    # Miejsce na testing program...
    
    # 5. Grading…
    print("Grading…")
    # Miejsce na grading…
    
    # 6. DONE!
    print("DONE!")


@shared_task
def execute_cs(solution_id):
    print(f"Executing C# for solution ID: {solution_id}...")
    
    # 1. Getting solution info...
    print("Getting solution info...")
    # Miejsce na getting solution info...
    
    # 2. Getting grouped tests...
    print("Getting grouped tests...")
    # Miejsce na getting grouped tests...
    
    # 3. Compile program...
    print("Compile program...")
    # Miejsce na compile program...
    
    # 4. Testing program...
    print("Testing program...")
    # Miejsce na testing program...
    
    # 5. Grading…
    print("Grading…")
    # Miejsce na grading…
    
    # 6. DONE!
    print("DONE!")
