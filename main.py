import sqlite3
import csv
import math
from datetime import datetime

DATABASE_NAME = "attendance_system.db"


class Database:
    @staticmethod
    def get_connection():
        conn = sqlite3.connect(DATABASE_NAME)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @staticmethod
    def initialize():
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subjects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    min_threshold REAL DEFAULT 75.0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    status TEXT CHECK(status IN ('Present', 'Absent')) NOT NULL,
                    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
                )
            """)
            conn.commit()


class AttendanceTracker:
    def __init__(self):
        Database.initialize()

    def add_subject(self, name: str, threshold: float = 75.0) -> bool:
        clean_name = name.strip()
        if not clean_name:
            print("[!] Subject name cannot be empty.")
            return False
        try:
            with Database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO subjects (name, min_threshold) VALUES (?, ?)",
                    (clean_name, threshold)
                )
                conn.commit()
                print(f"[✓] Subject '{clean_name}' registered with {threshold}% threshold.")
                return True
        except sqlite3.IntegrityError:
            print(f"[!] Error: Subject '{clean_name}' already exists.")
            return False

    def mark_attendance(self, subject_id: int, status: str, record_date: str = None) -> bool:
        if record_date is None:
            record_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            with Database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO attendance_records (subject_id, date, status) VALUES (?, ?, ?)",
                    (subject_id, record_date, status)
                )
                conn.commit()
                print(f"[✓] Recorded: {status} on {record_date}.")
                return True
        except sqlite3.Error as e:
            print(f"[!] Database error: {e}")
            return False

    def get_subjects(self):
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, min_threshold FROM subjects ORDER BY name ASC")
            return cursor.fetchall()

    def compute_metrics(self, subject_id: int, threshold: float):
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status FROM attendance_records WHERE subject_id = ?", 
                (subject_id,)
            )
            records = cursor.fetchall()

        total = len(records)
        if total == 0:
            return {
                "attended": 0,
                "total": 0,
                "percentage": 0.0,
                "status": "No Records",
                "action": "Mark your first lecture"
            }

        attended = sum(1 for (status,) in records if status == "Present")
        pct = (attended / total) * 100.0

        if pct >= threshold:
            max_bunkable = math.floor((100 * attended - threshold * total) / threshold)
            max_bunkable = max(0, max_bunkable)
            status_text = "Eligible"
            action_text = f"Can safely bunk {max_bunkable} lecture(s)" if max_bunkable > 0 else "On track (cannot miss next lecture)"
        else:
            needed = math.ceil((threshold * total - 100 * attended) / (100 - threshold))
            needed = max(1, needed)
            status_text = "Shortage (Defaulter)"
            action_text = f"Must attend next {needed} lecture(s) continuously"

        return {
            "attended": attended,
            "total": total,
            "percentage": pct,
            "status": status_text,
            "action": action_text
        }

    def display_dashboard(self):
        subjects = self.get_subjects()
        if not subjects:
            print("\n[i] No subjects found. Add a subject to get started.")
            return

        print("\n" + "=" * 90)
        print(f"{'ID':<4} | {'Subject':<22} | {'Attended/Total':<14} | {'Percentage':<10} | {'Status':<18} | {'Strategy Advice'}")
        print("-" * 90)

        for sub_id, name, threshold in subjects:
            metrics = self.compute_metrics(sub_id, threshold)
            att_str = f"{metrics['attended']}/{metrics['total']}"
            pct_str = f"{metrics['percentage']:.1f}%" if metrics['total'] > 0 else "N/A"
            print(f"{sub_id:<4} | {name:<22} | {att_str:<14} | {pct_str:<10} | {metrics['status']:<18} | {metrics['action']}")

        print("=" * 90 + "\n")

    def export_csv(self, filename: str = "attendance_summary.csv"):
        subjects = self.get_subjects()
        if not subjects:
            print("[!] No data to export.")
            return

        with open(filename, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Subject ID", "Subject Name", "Threshold (%)", "Attended", "Total Lectures", "Attendance (%)", "Status", "Recommendation"])
            
            for sub_id, name, threshold in subjects:
                metrics = self.compute_metrics(sub_id, threshold)
                writer.writerow([
                    sub_id,
                    name,
                    threshold,
                    metrics["attended"],
                    metrics["total"],
                    f"{metrics['percentage']:.2f}",
                    metrics["status"],
                    metrics["action"]
                ])
        print(f"[✓] Attendance report successfully exported to '{filename}'.")


def display_menu():
    print("""
======================================
  ACADEMIC ATTENDANCE & BUNK TRACKER
======================================
1. View Attendance Dashboard
2. Mark Lecture Attendance (Present / Absent)
3. Add New Subject
4. Export Report to CSV
5. Exit
""")


def main():
    tracker = AttendanceTracker()

    while True:
        display_menu()
        choice = input("Enter choice (1-5): ").strip()

        if choice == "1":
            tracker.display_dashboard()

        elif choice == "2":
            subjects = tracker.get_subjects()
            if not subjects:
                print("[!] Register at least one subject first.")
                continue

            print("\nAvailable Subjects:")
            for sub_id, name, _ in subjects:
                print(f"[{sub_id}] {name}")

            try:
                sub_id_input = int(input("\nEnter Subject ID: ").strip())
                valid_ids = [s[0] for s in subjects]
                if sub_id_input not in valid_ids:
                    print("[!] Invalid Subject ID selected.")
                    continue

                status_choice = input("Enter status ([P]resent / [A]bsent): ").strip().upper()
                if status_choice in ["P", "PRESENT"]:
                    tracker.mark_attendance(sub_id_input, "Present")
                elif status_choice in ["A", "ABSENT"]:
                    tracker.mark_attendance(sub_id_input, "Absent")
                else:
                    print("[!] Invalid status. Only 'P' or 'A' accepted.")
            except ValueError:
                print("[!] Please enter a valid numerical ID.")

        elif choice == "3":
            sub_name = input("Enter subject name (e.g., Computer Networks): ").strip()
            threshold_in = input("Enter target threshold percentage (default: 75.0): ").strip()
            
            threshold = 75.0
            if threshold_in:
                try:
                    threshold = float(threshold_in)
                    if not (0 < threshold <= 100):
                        print("[!] Threshold must be between 1 and 100. Defaulting to 75.0%.")
                        threshold = 75.0
                except ValueError:
                    print("[!] Invalid number. Defaulting to 75.0%.")

            tracker.add_subject(sub_name, threshold)

        elif choice == "4":
            filename = input("Enter output CSV filename (press Enter for 'attendance_summary.csv'): ").strip()
            if filename:
                if not filename.endswith(".csv"):
                    filename += ".csv"
                tracker.export_csv(filename)
            else:
                tracker.export_csv()

        elif choice == "5":
            print("Exiting tracker. All records saved.")
            break

        else:
            print("[!] Invalid choice. Enter a number between 1 and 5.")


if __name__ == "__main__":
    main()
