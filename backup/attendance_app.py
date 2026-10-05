import tkinter as tk
from tkinter import ttk
from tkinter import messagebox


def feature_preview():
    """Explain that the selected feature is not connected yet."""
    messagebox.showinfo(
        "Student Attendance Tracker",
        "We will connect this feature in the next steps."
    )


def confirm_exit():
    """Close the application after confirmation."""
    confirmed = messagebox.askyesno(
        "Confirm Exit",
        "All records will be lost. Exit?"
    )

    if confirmed:
        window.destroy()

def is_valid_name(name):
    """Check the allowed characters and punctuation in a name."""
    if not 1 <= len(name) <= 50:
        return False

    if not any(character.isalpha() for character in name):
        return False

    for index, character in enumerate(name):
        if character.isalpha() or character == " ":
            continue

        if character in ("-", "'"):
            if (
                index > 0
                and index < len(name) - 1
                and name[index - 1].isalpha()
                and name[index + 1].isalpha()
            ):
                continue

        return False

    return True


def open_add_student(students):
    """Open a form that validates and saves one student."""
    if len(students) >= 500:
        messagebox.showerror(
            "Class Full",
            "Maximum capacity is 500 students.",
            parent=window
        )
        return

    form = tk.Toplevel(window)
    form.title("Add Student")
    form.geometry("400x340")
    form.resizable(False, False)
    form.transient(window)
    form.grab_set()

    tk.Label(
        form,
        text="Add Student",
        font=("Arial", 18, "bold")
    ).pack(pady=15)

    tk.Label(form, text="Student ID (001–999):").pack()
    id_entry = ttk.Entry(form, width=30)
    id_entry.pack(pady=(5, 12))

    tk.Label(form, text="Full name (maximum 50 characters):").pack()
    name_entry = ttk.Entry(form, width=30)
    name_entry.pack(pady=(5, 12))

    tk.Label(form, text="Attendance status:").pack()
    status_box = ttk.Combobox(
        form,
        values=("Present", "Absent"),
        state="readonly",
        width=27
    )
    status_box.pack(pady=5)

    def save_student():
        """Validate the form and save the completed record."""
        student_id = id_entry.get().strip()
        name = " ".join(
            name_entry.get().replace("’", "'").split()
        )
        status = status_box.get()

        if (
            len(student_id) != 3
            or not student_id.isascii()
            or not student_id.isdigit()
            or student_id == "000"
        ):
            messagebox.showerror(
                "Invalid ID",
                "Enter exactly 3 digits from 001 to 999.",
                parent=form
            )
            id_entry.focus_set()
            return

        if student_id in students:
            messagebox.showerror(
                "Duplicate ID",
                "This ID already exists. Enter a different Student ID.",
                parent=form
            )
            id_entry.focus_set()
            return

        if not is_valid_name(name):
            messagebox.showerror(
                "Invalid Name",
                "Enter 1–50 characters using letters, spaces, "
                "hyphens or apostrophes, with at least one letter. "
                "Hyphens and apostrophes must have a letter "
                "directly on both sides.",
                parent=form
            )
            name_entry.focus_set()
            return

        if status not in ("Present", "Absent"):
            messagebox.showerror(
                "Missing Status",
                "Select Present or Absent.",
                parent=form
            )
            status_box.focus_set()
            return

        for student in students.values():
            if student["name"].casefold() == name.casefold():
                confirmed = messagebox.askyesno(
                    "Duplicate Name",
                    "A student with this name already exists.\n"
                    "Add another student with the same name?",
                    parent=form
                )

                if not confirmed:
                    name_entry.focus_set()
                    return

                break

        students[student_id] = {
            "name": name,
            "status": status
        }

        messagebox.showinfo(
            "Student Saved",
            f"{student_id}: {name} added as {status}.\n"
            f"Total students: {len(students)}",
            parent=form
        )
        form.destroy()

    buttons = tk.Frame(form)
    buttons.pack(pady=20)

    ttk.Button(
        buttons,
        text="Save",
        command=save_student
    ).pack(side="left", padx=5)

    ttk.Button(
        buttons,
        text="Cancel",
        command=form.destroy
    ).pack(side="left", padx=5)

    id_entry.focus_set()

window = tk.Tk()
window.title("Student Attendance Tracker")
window.geometry("480x580")
window.resizable(False, False)
window.configure(bg="#f3f4f6")

title = tk.Label(
    window,
    text="Student Attendance Tracker",
    font=("Arial", 20, "bold"),
    bg="#f3f4f6",
    fg="#1f2937"
)
title.pack(pady=(30, 8))

subtitle = tk.Label(
    window,
    text="Manage attendance for one class session",
    font=("Arial", 11),
    bg="#f3f4f6",
    fg="#4b5563"
)
subtitle.pack(pady=(0, 20))

menu_options = [
    "Record Attendance",
    "Add Student",
    "View Attendance",
    "Search Student",
    "Edit Attendance",
    "View Summary"
]

def open_view_attendance(students):
    """Display saved students in a table sorted by ID."""
    if not students:
        messagebox.showinfo(
            "No Records",
            "No attendance records found. Add students first.",
            parent=window
        )
        return

    view = tk.Toplevel(window)
    view.title("View Attendance")
    view.geometry("650x400")
    view.transient(window)
    view.grab_set()

    tk.Label(
        view,
        text="Attendance Records",
        font=("Arial", 18, "bold")
    ).pack(pady=15)

    table_frame = ttk.Frame(view)
    table_frame.pack(fill="both", expand=True, padx=15)

    table = ttk.Treeview(
        table_frame,
        columns=("id", "name", "status"),
        show="headings"
    )

    table.heading("id", text="Student ID")
    table.heading("name", text="Full Name")
    table.heading("status", text="Status")

    table.column("id", width=90, anchor="center")
    table.column("name", width=350, anchor="w")
    table.column("status", width=110, anchor="center")

    scrollbar = ttk.Scrollbar(
        table_frame,
        orient="vertical",
        command=table.yview
    )
    table.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    table.pack(side="left", fill="both", expand=True)

    for student_id in sorted(students):
        student = students[student_id]

        table.insert(
            "",
            "end",
            values=(
                student_id,
                student["name"],
                student["status"]
            )
        )

    ttk.Label(
        view,
        text=f"Total students: {len(students)}"
    ).pack(pady=10)

    ttk.Button(
        view,
        text="Close",
        command=view.destroy
    ).pack(pady=(0, 15))

def open_view_summary(students):
    """Display attendance statistics and absent students."""
    if not students:
        messagebox.showinfo(
            "No Records",
            "No attendance records found. Add students first.",
            parent=window
        )
        return

    total = len(students)
    present = 0

    for student in students.values():
        if student["status"] == "Present":
            present += 1

    absent = total - present
    attendance_rate = (present / total) * 100

    summary = tk.Toplevel(window)
    summary.title("Attendance Summary")
    summary.geometry("550x480")
    summary.transient(window)
    summary.grab_set()

    tk.Label(
        summary,
        text="Attendance Summary",
        font=("Arial", 18, "bold")
    ).pack(pady=15)

    statistics = (
        f"Total students: {total}\n"
        f"Present: {present}\n"
        f"Absent: {absent}\n"
        f"Attendance rate: {attendance_rate:.2f}%"
    )

    ttk.Label(
        summary,
        text=statistics,
        font=("Arial", 12),
        justify="left"
    ).pack(pady=10)

    if absent == 0:
        ttk.Label(
            summary,
            text="No absent students."
        ).pack(pady=20)

    else:
        ttk.Label(
            summary,
            text="Absent students",
            font=("Arial", 12, "bold")
        ).pack(pady=10)

        table_frame = ttk.Frame(summary)
        table_frame.pack(fill="both", expand=True, padx=15)

        table = ttk.Treeview(
            table_frame,
            columns=("id", "name"),
            show="headings"
        )

        table.heading("id", text="Student ID")
        table.heading("name", text="Full Name")

        table.column("id", width=90, anchor="center")
        table.column("name", width=350, anchor="w")

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=table.yview
        )
        table.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        table.pack(side="left", fill="both", expand=True)

        for student_id in sorted(students):
            student = students[student_id]

            if student["status"] == "Absent":
                table.insert(
                    "",
                    "end",
                    values=(student_id, student["name"])
                )

    ttk.Button(
        summary,
        text="Close",
        command=summary.destroy
    ).pack(pady=15)

def open_edit_attendance(students):
    """Find a student by ID and update their attendance status."""
    if not students:
        messagebox.showinfo(
            "No Records",
            "No attendance records found. Add students first.",
            parent=window
        )
        return

    form = tk.Toplevel(window)
    form.title("Edit Attendance")
    form.geometry("420x380")
    form.resizable(False, False)
    form.transient(window)
    form.grab_set()

    # Remember which student was found.
    selected_id = None

    tk.Label(
        form,
        text="Edit Attendance",
        font=("Arial", 18, "bold")
    ).pack(pady=15)

    ttk.Label(form, text="Student ID (001–999):").pack()

    id_entry = ttk.Entry(form, width=30)
    id_entry.pack(pady=5)

    details_label = ttk.Label(
        form,
        text="Find a student to see their current status.",
        justify="center",
        wraplength=380
    )

    status_box = ttk.Combobox(
        form,
        values=("Present", "Absent"),
        state="disabled",
        width=27
    )

    def find_student():
        """Validate the ID and display the matching student."""
        nonlocal selected_id

        selected_id = None
        status_box.set("")
        status_box.configure(state="disabled")
        save_button.configure(state="disabled")
        details_label.configure(text="No student selected.")

        student_id = id_entry.get().strip()

        if (
            len(student_id) != 3
            or not student_id.isascii()
            or not student_id.isdigit()
            or student_id == "000"
        ):
            messagebox.showerror(
                "Invalid ID",
                "Enter exactly 3 digits from 001 to 999.",
                parent=form
            )
            return

        if student_id not in students:
            messagebox.showinfo(
                "Not Found",
                "No student has this ID. Enter an existing Student ID.",
                parent=form
            )
            return

        selected_id = student_id
        student = students[selected_id]

        details_label.configure(
            text=(
                f"ID: {selected_id}\n"
                f"Name: {student['name']}\n"
                f"Current status: {student['status']}"
            )
        )

        status_box.configure(state="readonly")
        status_box.set(student["status"])
        save_button.configure(state="normal")

    def save_changes():
        """Update only the student displayed in the form."""
        if selected_id is None:
            return

        if id_entry.get().strip() != selected_id:
            messagebox.showerror(
                "Find Student Again",
                "The ID field has changed. Click Find before saving.",
                parent=form
            )
            return

        new_status = status_box.get()
        student = students[selected_id]

        if new_status not in ("Present", "Absent"):
            messagebox.showerror(
                "Invalid Status",
                "Select Present or Absent.",
                parent=form
            )
            return

        if new_status == student["status"]:
            messagebox.showinfo(
                "No Change",
                f"The student is already {new_status}.",
                parent=form
            )
            return

        student["status"] = new_status

        messagebox.showinfo(
            "Attendance Updated",
            f"{selected_id}: {student['name']} is now {new_status}.",
            parent=form
        )
        form.destroy()

    ttk.Button(
        form,
        text="Find",
        command=find_student
    ).pack(pady=8)

    details_label.pack(pady=10)

    ttk.Label(form, text="New attendance status:").pack()
    status_box.pack(pady=5)

    buttons = ttk.Frame(form)
    buttons.pack(pady=15)

    save_button = ttk.Button(
        buttons,
        text="Save Changes",
        command=save_changes,
        state="disabled"
    )
    save_button.pack(side="left", padx=5)

    ttk.Button(
        buttons,
        text="Cancel",
        command=form.destroy
    ).pack(side="left", padx=5)

    id_entry.focus_set()

def open_search_student(students):
    """Search by exact ID or exact cleaned, case-insensitive name."""
    if not students:
        messagebox.showinfo(
            "No Records",
            "No attendance records found. Add students first.",
            parent=window
        )
        return

    form = tk.Toplevel(window)
    form.title("Search Student")
    form.geometry("650x430")
    form.transient(window)
    form.grab_set()

    tk.Label(
        form,
        text="Search Student",
        font=("Arial", 18, "bold")
    ).pack(pady=15)

    search_frame = ttk.Frame(form)
    search_frame.pack(pady=5)

    ttk.Label(search_frame, text="Search by:").grid(
        row=0, column=0, padx=5
    )

    search_type = ttk.Combobox(
        search_frame,
        values=("Student ID", "Full Name"),
        state="readonly",
        width=15
    )
    search_type.set("Student ID")
    search_type.grid(row=0, column=1, padx=5)

    query_entry = ttk.Entry(search_frame, width=30)
    query_entry.grid(row=0, column=2, padx=5)

    ttk.Label(
        form,
        text="Enter a 3-digit ID or the complete name."
    ).pack(pady=5)

    result_label = ttk.Label(form, text="No search performed yet.")

    table_frame = ttk.Frame(form)
    table = ttk.Treeview(
        table_frame,
        columns=("id", "name", "status"),
        show="headings"
    )

    table.heading("id", text="Student ID")
    table.heading("name", text="Full Name")
    table.heading("status", text="Status")

    table.column("id", width=90, anchor="center")
    table.column("name", width=350, anchor="w")
    table.column("status", width=110, anchor="center")

    scrollbar = ttk.Scrollbar(
        table_frame,
        orient="vertical",
        command=table.yview
    )
    table.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    table.pack(side="left", fill="both", expand=True)

    def search():
        """Validate the search input and display all matches."""
        for row in table.get_children():
            table.delete(row)

        result_label.configure(text="")

        query = query_entry.get().strip()
        matches = []

        if search_type.get() == "Student ID":
            if (
                len(query) != 3
                or not query.isascii()
                or not query.isdigit()
                or query == "000"
            ):
                messagebox.showerror(
                    "Invalid ID",
                    "Enter exactly 3 digits from 001 to 999.",
                    parent=form
                )
                return

            if query in students:
                matches.append(query)

        else:
            query = " ".join(query.replace("’", "'").split())

            if not is_valid_name(query):
                messagebox.showerror(
                    "Invalid Name",
                    "Enter a complete name of 1–50 characters, "
                    "using letters, spaces, hyphens or apostrophes. "
                    "Punctuation must be directly between letters.",
                    parent=form
                )
                return

            for student_id in sorted(students):
                student = students[student_id]

                if student["name"].casefold() == query.casefold():
                    matches.append(student_id)

        if not matches:
            result_label.configure(text="No matching students found.")
            return

        for student_id in matches:
            student = students[student_id]

            table.insert(
                "",
                "end",
                values=(
                    student_id,
                    student["name"],
                    student["status"]
                )
            )

        result_label.configure(
            text=f"Matching students: {len(matches)}"
        )

    ttk.Button(
        form,
        text="Search",
        command=search
    ).pack(pady=8)

    result_label.pack(pady=5)
    table_frame.pack(fill="both", expand=True, padx=15)

    ttk.Button(
        form,
        text="Close",
        command=form.destroy
    ).pack(pady=15)

    query_entry.focus_set()


def build_menu():
    """Create the menu and keep student records for this session."""
    students = {}

    for option in menu_options:
        if option == "Add Student":
            action = lambda: open_add_student(students)

        elif option == "View Attendance":
            action = lambda: open_view_attendance(students)
            
        elif option == "View Summary":
            action = lambda: open_view_summary(students)
            
        elif option == "Edit Attendance":
            action = lambda: open_edit_attendance(students)
            
        elif option == "Search Student":
            action = lambda: open_search_student(students)

        else:
            action = feature_preview

        button = tk.Button(
            window,
            text=option,
            font=("Arial", 12),
            width=28,
            pady=8,
            command=action
        )
        button.pack(pady=5)
        
build_menu()

exit_button = tk.Button(
    window,
    text="Exit",
    font=("Arial", 12),
    width=28,
    pady=8,
    command=confirm_exit
)
exit_button.pack(pady=5)

window.protocol("WM_DELETE_WINDOW", confirm_exit)

window.mainloop()