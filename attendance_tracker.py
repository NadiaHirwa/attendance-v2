def show_menu():
    """Display the main menu."""
    print("\n===== STUDENT ATTENDANCE TRACKER =====")
    print("1. Record Attendance")
    print("2. Add Student")
    print("3. View Attendance")
    print("4. Search Student")
    print("5. Edit Attendance")
    print("6. View Summary")
    print("7. Exit")


def confirm_exit():
    """Ask whether the user wants to exit."""
    while True:
        answer = input(
            "All records will be lost. Exit? [Y/N, 0 to cancel]: "
        ).strip().lower()

        if answer in ("y", "yes"):
            return True

        if answer in ("n", "no", "0"):
            return False

        print("Invalid answer. Enter Y, Yes, N, No, or 0.")


def get_student_id(students):
    """Ask for a valid, unused student ID, or return None to cancel."""
    while True:
        student_id = input(
            "Enter Student ID [001-999, 0 to cancel]: "
        ).strip()

        if student_id == "0":
            return None

        if (
            len(student_id) != 3
            or not student_id.isascii()
            or not student_id.isdigit()
            or student_id == "000"
        ):
            print(
                "Invalid ID. Enter exactly 3 digits from 001 to 999."
            )
            continue

        if student_id in students:
            print(
                "This ID already exists. Enter a different Student ID."
            )
            continue

        return student_id

def get_status():
    """Ask for a valid attendance status, or return None to cancel."""
    while True:
        status = input(
            "Enter status [P/A or Present/Absent, 0 to cancel]: "
        ).strip().lower()

        if status == "0":
            return None

        if status in ("p", "present"):
            return "Present"

        if status in ("a", "absent"):
            return "Absent"

        print("Invalid status. Enter P, A, Present, or Absent.")

def clean_name(name):
    """Remove extra spaces and standardize apostrophes."""
    return " ".join(name.replace("’", "'").split())


def get_student_name():
    """Ask for a valid student name, or return None to cancel."""
    while True:
        name = input(
            "Enter full name [max 50 characters, 0 to cancel]: "
        )
        name = clean_name(name)

        if name == "0":
            return None

        if not name or len(name) > 50:
            print(
                "Invalid name. Enter 1 to 50 characters "
                "including at least one letter."
            )
            continue

        has_letter = False
        valid = True

        for index, character in enumerate(name):
            if character.isalpha():
                has_letter = True

            elif character == " ":
                continue

            elif character in ("-", "'"):
                if (
                    index == 0
                    or index == len(name) - 1
                    or not name[index - 1].isalpha()
                    or not name[index + 1].isalpha()
                ):
                    valid = False
                    break

            else:
                valid = False
                break

        if not valid or not has_letter:
            print(
                "Invalid name. Use letters, spaces, hyphens, "
                "or apostrophes, with at least one letter. "
                "Each hyphen or apostrophe must have "
                "a letter directly on both sides."
            )
            continue

        return name  


def get_yes_no(prompt):
    """Return True for yes, False for no, or None to cancel."""
    while True:
        answer = input(
            f"{prompt} [Y/N, 0 to cancel]: "
        ).strip().lower()

        if answer == "0":
            return None

        if answer in ("y", "yes"):
            return True

        if answer in ("n", "no"):
            return False

        print("Invalid answer. Enter Y, Yes, N, No, or 0.")

def add_student(students):
    """Validate and save one student, or cancel without saving."""
    if len(students) >= 500:
        print("Class capacity reached. Maximum: 500 students.")
        return

    student_id = get_student_id(students)

    if student_id is None:
        print("Adding student cancelled.")
        return

    while True:
        name = get_student_name()

        if name is None:
            print("Adding student cancelled.")
            return

        duplicate_name = False

        for student in students.values():
            if student["name"].casefold() == name.casefold():
                duplicate_name = True
                break

        if duplicate_name:
            print("Warning: a student with this name already exists.")
            confirmed = get_yes_no(
                "Add another student with the same name?"
            )

            if confirmed is None:
                print("Adding student cancelled.")
                return

            if not confirmed:
                print("Name not accepted. Enter a different name.")
                continue

        break

    status = get_status()

    if status is None:
        print("Adding student cancelled.")
        return

    students[student_id] = {
        "name": name,
        "status": status
    }

    print(f"Student {student_id}: {name} added as {status}.")
    print("Total students:", len(students))

def view_attendance(students):
    """Display all student records sorted by Student ID."""
    if not students:
        print("No attendance records found. Record or add students first.")
        return

    print("\n===== ATTENDANCE RECORDS =====")
    print(f"{'ID':<5} {'Full name':<50} {'Status':<7}")
    print("-" * 64)

    for student_id in sorted(students):
        student = students[student_id]
        print(
            f"{student_id:<5} "
            f"{student['name']:<50} "
            f"{student['status']:<7}"
        )

    print("-" * 64)
    print("Total students:", len(students))

def view_summary(students):
    """Display attendance totals, rate, and absent students."""
    if not students:
        print("No attendance records found. Record or add students first.")
        return

    total = len(students)
    present = 0

    for student in students.values():
        if student["status"] == "Present":
            present += 1

    absent = total - present
    attendance_rate = (present / total) * 100

    print("\n===== ATTENDANCE SUMMARY =====")
    print("Total students:", total)
    print("Present:", present)
    print("Absent:", absent)
    print(f"Attendance rate: {attendance_rate:.2f}%")

    if absent == 0:
        print("No absent students.")
        return

    print("\nAbsent students:")
    print(f"{'ID':<5} {'Full name':<50}")
    print("-" * 56)

    for student_id in sorted(students):
        student = students[student_id]

        if student["status"] == "Absent":
            print(f"{student_id:<5} {student['name']:<50}")


def main():
    """Run the attendance tracker."""
    students = {}

    while True:
        try:
            show_menu()
            choice = input("Choose an option [1-7]: ").strip()

            if choice == "1":
                student_id = get_student_id(students)

                if student_id is None:
                    print("Recording cancelled.")
                    continue

                name = get_student_name()

                if name is None:
                    print("Recording cancelled.")
                    continue

                status = get_status()

                if status is None:
                    print("Recording cancelled.")
                    continue

                print("\nValidated student details:")
                print("Student ID:", student_id)
                print("Full name:", name)
                print("Status:", status)

            elif choice == "2":
                add_student(students)

            elif choice == "3":
                view_attendance(students)

            elif choice in ("4", "5"):
                print("We will implement this feature next.")

            elif choice == "6":
                view_summary(students)

            elif choice == "7":
                if confirm_exit():
                    print("Goodbye!")
                    break

                print("Exit cancelled. Returning to the main menu.")

            else:
                print("Invalid choice. Enter a number from 1 to 7.")

        except KeyboardInterrupt:
            print("\nAction cancelled. Returning to the main menu.")

        except EOFError:
            print("\nInput closed. Exiting. Any records will be lost.")
            break

if __name__ == "__main__":
    main()