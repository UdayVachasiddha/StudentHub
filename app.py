import csv
import io
import os
import uuid
from datetime import date
from functools import wraps

from flask import Flask, Response, flash, redirect, render_template, request, send_from_directory, session, url_for
from mysql.connector import Error
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from database import get_connection

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "studenthub-local-development"),
    UPLOAD_FOLDER=os.path.join(app.root_path, "uploads"),
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    TEMPLATES_AUTO_RELOAD=True,
    SEND_FILE_MAX_AGE_DEFAULT=0,
)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

@app.after_request
def add_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

MANAGERS = {"admin", "staff"}
ACADEMIC_STAFF = {"admin", "staff", "teacher"}
ALLOWED_DOCUMENTS = {"pdf", "png", "jpg", "jpeg", "doc", "docx"}


def query_all(sql, params=()):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def query_one(sql, params=()):
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        connection.commit()
        return cursor.lastrowid, cursor.rowcount
    finally:
        cursor.close()
        connection.close()


def current_user():
    return session.get("user")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("login"))
            if user["role"] not in roles:
                flash("You do not have permission for that action.", "error")
                return redirect(url_for("home"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def log_activity(action, entity_type, entity_id=None):
    user = current_user()
    try:
        execute(
            "INSERT INTO activity_history (user_id, action, entity_type, entity_id) VALUES (%s, %s, %s, %s)",
            (user["id"] if user else None, action, entity_type, entity_id),
        )
    except Error:
        pass


def notify(role, message, category="general"):
    try:
        execute(
            "INSERT INTO notifications (recipient_role, message, category) VALUES (%s, %s, %s)",
            (role, message, category),
        )
    except Error:
        pass


def avatar(name):
    words = name.split()
    return "".join(word[0] for word in words[:2]).upper() or "ST"


def fetch_courses():
    return query_all(
        """SELECT c.*, COUNT(s.id) AS enrolled
           FROM courses c LEFT JOIN students s ON s.course_id = c.id
           GROUP BY c.id ORDER BY c.name"""
    )


def fetch_student(student_id):
    student = query_one(
        """SELECT s.*, CONCAT('STU-', s.id + 100) AS student_code,
                  c.name AS course_name, c.instructor
           FROM students s LEFT JOIN courses c ON c.id = s.course_id
           WHERE s.id = %s""",
        (student_id,),
    )
    if student:
        student["avatar"] = avatar(student["name"])
    return student


from datetime import date, datetime

@app.context_processor
def template_context():
    user = current_user()
    unread = 0
    if user:
        try:
            row = query_one("SELECT COUNT(*) AS count FROM notifications WHERE recipient_role = %s AND is_read = FALSE", (user["role"],))
            unread = row["count"] if row else 0
        except Error:
            pass
    return {
        "current_user": user,
        "unread_notifications": unread,
        "can_manage": user and user["role"] in MANAGERS,
        "can_teach": user and user["role"] in ACADEMIC_STAFF,
        "now": datetime.now(),
    }



@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("home"))
    if request.method == "POST":
        user = query_one("SELECT id, username, password_hash, full_name, role, student_id FROM users WHERE username = %s", (request.form.get("username", "").strip(),))
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session["user"] = {key: user[key] for key in ("id", "username", "full_name", "role", "student_id")}
            log_activity("Signed in", "user", user["id"])
            return redirect(request.args.get("next") or url_for("home"))
        flash("Check your username and password.", "error")
    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user():
        return redirect(url_for("home"))
    courses = fetch_courses()
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")
        course_id = request.form.get("course_id", type=int)
        email = request.form.get("email", "").strip()

        course = query_one("SELECT name FROM courses WHERE id = %s", (course_id,)) if course_id else None
        if not full_name or not username or not email or not course:
            flash("Complete every field and choose a course.", "error")
        elif len(password) < 8:
            flash("Use a password with at least 8 characters.", "error")
        elif password != confirmation:
            flash("The password confirmation does not match.", "error")
        else:
            try:
                student_id, _ = execute(
                    "INSERT INTO students (name, course, course_id, status, email) VALUES (%s, %s, %s, 'Pending', %s)",
                    (full_name, course["name"], course_id, email),
                )
                execute(
                    "INSERT INTO users (username, password_hash, full_name, role, student_id) VALUES (%s, %s, %s, 'student', %s)",
                    (username, generate_password_hash(password), full_name, student_id),
                )
                notify("staff", f"New student signup: {full_name} is awaiting review.", "signup")
                flash("Your account was created. Sign in to view your profile.", "success")
                return redirect(url_for("login"))
            except Error:
                flash("That username or email is already in use. Try another one.", "error")
    return render_template("signup.html", courses=courses)


@app.get("/")
@login_required
def home():
    try:
        metrics = query_one("""SELECT COUNT(*) AS total_students, SUM(status = 'Active') AS active_students,
                                      COUNT(DISTINCT course_id) AS total_courses FROM students""")
        metrics = {key: value or 0 for key, value in metrics.items()}
        recent = query_all("""SELECT s.id, s.name, s.status, CONCAT('STU-', s.id + 100) AS student_code,
                                    COALESCE(c.name, s.course) AS course_name FROM students s
                             LEFT JOIN courses c ON c.id = s.course_id ORDER BY s.id DESC LIMIT 5""")
        course_chart = fetch_courses()[:6]
        max_enrolled = max((course["enrolled"] for course in course_chart), default=1)
        for course in course_chart:
            course["percentage"] = round(course["enrolled"] / max_enrolled * 100) if max_enrolled else 0
            
        attendance_trend = query_all("""
            SELECT attendance_date,
                   SUM(status='Present') AS present,
                   SUM(status='Late') AS late,
                   COUNT(student_id) as total
            FROM attendance
            GROUP BY attendance_date
            ORDER BY attendance_date DESC
            LIMIT 7
        """)
        attendance_trend.reverse()
        if attendance_trend:
            max_att = max(day["total"] for day in attendance_trend)
            for day in attendance_trend:
                day["present_pct"] = round(day["present"] / day["total"] * 100) if day["total"] else 0
                day["late_pct"] = round(day["late"] / day["total"] * 100) if day["total"] else 0
                day["height_pct"] = round(day["total"] / max_att * 100) if max_att else 0

    except Error:
        metrics, recent, course_chart, attendance_trend = {"total_students": 0, "active_students": 0, "total_courses": 0}, [], [], []
        flash("MySQL is not connected yet. Check your database configuration.", "error")
    return render_template("index.html", recent=recent, course_chart=course_chart, attendance_trend=attendance_trend, **metrics)


@app.get("/students")
@login_required
def students():
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    course_id = request.args.get("course", type=int)
    sort = request.args.get("sort", "newest")
    ordering = {"newest": "s.id DESC", "name": "s.name ASC", "course": "course_name ASC"}.get(sort, "s.id DESC")
    where, params = [], []
    if search:
        where.append("(s.name LIKE %s OR CONCAT('STU-', s.id + 100) LIKE %s OR s.email LIKE %s)")
        params.extend([f"%{search}%"] * 3)
    if status in {"Active", "Pending"}:
        where.append("s.status = %s")
        params.append(status)
    if course_id:
        where.append("s.course_id = %s")
        params.append(course_id)
    clause = " WHERE " + " AND ".join(where) if where else ""
    roster = query_all(f"""SELECT s.id, s.name, s.status, CONCAT('STU-', s.id + 100) AS student_code,
                                  COALESCE(c.name, s.course) AS course_name FROM students s
                           LEFT JOIN courses c ON c.id = s.course_id {clause} ORDER BY {ordering}""", tuple(params))
    for student in roster:
        student["avatar"] = avatar(student["name"])
    return render_template("students.html", students=roster, courses=fetch_courses(), filters={"q": search, "status": status, "course": course_id, "sort": sort})


@app.route("/students/add", methods=["GET", "POST"])
@roles_required(*MANAGERS)
def add_student():
    courses = fetch_courses()
    if request.method == "POST":
        name, course_id = request.form.get("name", "").strip(), request.form.get("course_id", type=int)
        if not name or not course_id:
            flash("A student name and course are required.", "error")
            return render_template("student_form.html", student=None, courses=courses, mode="add")
        course = query_one("SELECT name FROM courses WHERE id = %s", (course_id,))
        if not course:
            flash("Choose a valid course.", "error")
            return render_template("student_form.html", student=None, courses=courses, mode="add")
        student_id, _ = execute("""INSERT INTO students (name, course, course_id, status, email, phone, date_of_birth, guardian_name, address)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                                (name, course["name"], course_id, request.form.get("status", "Active"), request.form.get("email") or None, request.form.get("phone") or None, request.form.get("date_of_birth") or None, request.form.get("guardian_name") or None, request.form.get("address") or None))
        log_activity(f"Added student {name}", "student", student_id)
        notify("staff", f"{name} was added to the student roster.", "student")
        flash(f"{name} was added successfully.", "success")
        return redirect(url_for("student_profile", student_id=student_id))
    return render_template("student_form.html", student=None, courses=courses, mode="add")


@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@roles_required(*MANAGERS)
def edit_student(student_id):
    student = fetch_student(student_id)
    if not student:
        flash("That student no longer exists.", "error")
        return redirect(url_for("students"))
    courses = fetch_courses()
    if request.method == "POST":
        name, course_id = request.form.get("name", "").strip(), request.form.get("course_id", type=int)
        course = query_one("SELECT name FROM courses WHERE id = %s", (course_id,)) if course_id else None
        if not name or not course:
            flash("A student name and valid course are required.", "error")
            student.update(request.form)
            return render_template("student_form.html", student=student, courses=courses, mode="edit")
        execute("""UPDATE students SET name=%s, course=%s, course_id=%s, status=%s, email=%s, phone=%s,
                  date_of_birth=%s, guardian_name=%s, address=%s WHERE id=%s""",
                (name, course["name"], course_id, request.form.get("status", "Active"), request.form.get("email") or None, request.form.get("phone") or None, request.form.get("date_of_birth") or None, request.form.get("guardian_name") or None, request.form.get("address") or None, student_id))
        log_activity(f"Updated student {name}", "student", student_id)
        flash(f"{name} was updated successfully.", "success")
        return redirect(url_for("student_profile", student_id=student_id))
    return render_template("student_form.html", student=student, courses=courses, mode="edit")


@app.post("/students/<int:student_id>/delete")
@roles_required("admin")
def delete_student(student_id):
    student = fetch_student(student_id)
    _, deleted = execute("DELETE FROM students WHERE id = %s", (student_id,))
    if deleted:
        log_activity(f"Deleted student {student['name']}", "student", student_id)
        flash("Student record was deleted.", "success")
    else:
        flash("That student no longer exists.", "error")
    return redirect(url_for("students"))


@app.get("/students/<int:student_id>")
@login_required
def student_profile(student_id):
    user = current_user()
    if user["role"] == "student" and user.get("student_id") != student_id:
        flash("You can only view your own profile.", "error")
        return redirect(url_for("home"))
    student = fetch_student(student_id)
    if not student:
        flash("That student no longer exists.", "error")
        return redirect(url_for("students"))
    attendance = query_one("""SELECT COUNT(*) AS total, SUM(status='Present') AS present, SUM(status='Late') AS late
                              FROM attendance WHERE student_id=%s""", (student_id,))
    attendance["percentage"] = round(((attendance["present"] or 0) + (attendance["late"] or 0)) / attendance["total"] * 100) if attendance["total"] else 0
    assessments = query_all("SELECT * FROM assessments WHERE student_id=%s ORDER BY recorded_at DESC", (student_id,))
    documents = query_all("SELECT * FROM documents WHERE student_id=%s ORDER BY uploaded_at DESC", (student_id,))
    average = round(sum(float(a["score"]) / float(a["max_score"]) * 100 for a in assessments) / len(assessments), 1) if assessments else None
    return render_template("student_profile.html", student=student, attendance=attendance, assessments=assessments, documents=documents, average=average)


@app.route("/courses", methods=["GET", "POST"])
@roles_required(*MANAGERS)
def courses():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        instructor = request.form.get("instructor", "").strip()
        if not name or not instructor:
            flash("A course name and instructor are required.", "error")
        else:
            try:
                course_id, _ = execute("INSERT INTO courses (name, instructor, duration_weeks, capacity) VALUES (%s, %s, %s, %s)", (name, instructor, request.form.get("duration_weeks", type=int) or 12, request.form.get("capacity", type=int) or 30))
                log_activity(f"Created course {name}", "course", course_id)
                flash("Course created.", "success")
            except Error:
                flash("That course name already exists.", "error")
        return redirect(url_for("courses"))
    return render_template("courses.html", courses=fetch_courses())


@app.route("/attendance", methods=["GET", "POST"])
@roles_required(*ACADEMIC_STAFF)
def attendance():
    selected_date = request.values.get("date", date.today().isoformat())
    if request.method == "POST":
        for student_id, status in request.form.items():
            if student_id.startswith("student_") and status in {"Present", "Absent", "Late"}:
                execute("""INSERT INTO attendance (student_id, attendance_date, status, recorded_by) VALUES (%s, %s, %s, %s)
                           ON DUPLICATE KEY UPDATE status=VALUES(status), recorded_by=VALUES(recorded_by)""",
                        (student_id.removeprefix("student_"), selected_date, status, current_user()["id"]))
        log_activity(f"Recorded attendance for {selected_date}", "attendance")
        flash("Attendance saved.", "success")
        return redirect(url_for("attendance", date=selected_date))
    roster = query_all("""SELECT s.id, s.name, COALESCE(c.name, s.course) AS course_name, a.status
                          FROM students s LEFT JOIN courses c ON c.id=s.course_id
                          LEFT JOIN attendance a ON a.student_id=s.id AND a.attendance_date=%s ORDER BY s.name""", (selected_date,))
    return render_template("attendance.html", students=roster, selected_date=selected_date)


@app.post("/students/<int:student_id>/assessments")
@roles_required(*ACADEMIC_STAFF)
def add_assessment(student_id):
    title = request.form.get("title", "").strip()
    score, max_score = request.form.get("score", type=float), request.form.get("max_score", type=float)
    if not title or score is None or max_score is None or max_score <= 0 or score < 0 or score > max_score:
        flash("Enter a valid assessment name and score.", "error")
    else:
        execute("INSERT INTO assessments (student_id, title, score, max_score, recorded_at) VALUES (%s, %s, %s, %s, %s)", (student_id, title, score, max_score, request.form.get("recorded_at") or date.today()))
        log_activity(f"Recorded {title}", "assessment", student_id)
        flash("Assessment recorded.", "success")
    return redirect(url_for("student_profile", student_id=student_id))


@app.post("/students/<int:student_id>/documents")
@roles_required(*ACADEMIC_STAFF)
def upload_document(student_id):
    uploaded = request.files.get("document")
    title = request.form.get("title", "").strip()
    if not uploaded or not uploaded.filename or not title:
        flash("Give the document a title and choose a file.", "error")
        return redirect(url_for("student_profile", student_id=student_id))
    extension = uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
    if extension not in ALLOWED_DOCUMENTS:
        flash("Allowed documents: PDF, PNG, JPG, DOC, and DOCX.", "error")
        return redirect(url_for("student_profile", student_id=student_id))
    original = secure_filename(uploaded.filename)
    stored = f"{uuid.uuid4().hex}.{extension}"
    uploaded.save(os.path.join(app.config["UPLOAD_FOLDER"], stored))
    execute("INSERT INTO documents (student_id, title, stored_filename, original_filename) VALUES (%s, %s, %s, %s)", (student_id, title, stored, original))
    log_activity(f"Uploaded {title}", "document", student_id)
    flash("Document uploaded.", "success")
    return redirect(url_for("student_profile", student_id=student_id))


@app.get("/documents/<int:document_id>/download")
@login_required
def download_document(document_id):
    document = query_one("SELECT * FROM documents WHERE id=%s", (document_id,))
    if not document:
        flash("Document not found.", "error")
        return redirect(url_for("students"))
    return send_from_directory(app.config["UPLOAD_FOLDER"], document["stored_filename"], as_attachment=True, download_name=document["original_filename"])


@app.get("/exports/students.csv")
@roles_required(*MANAGERS)
def export_students_csv():
    rows = query_all("""SELECT CONCAT('STU-', s.id+100) AS student_id, s.name, s.email, s.phone,
                              COALESCE(c.name, s.course) AS course, s.status FROM students s LEFT JOIN courses c ON c.id=s.course_id ORDER BY s.name""")
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=["student_id", "name", "email", "phone", "course", "status"])
    writer.writeheader(); writer.writerows(rows)
    return Response(stream.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=studenthub-students.csv"})


@app.get("/exports/students.pdf")
@roles_required(*MANAGERS)
def export_students_pdf():
    rows = query_all("""SELECT CONCAT('STU-', s.id+100) AS student_id, s.name, COALESCE(c.name, s.course) AS course, s.status
                              FROM students s LEFT JOIN courses c ON c.id=s.course_id ORDER BY s.name""")
    output = io.BytesIO(); pdf = canvas.Canvas(output, pagesize=A4); width, height = A4; y = height - 54
    pdf.setFont("Helvetica-Bold", 16); pdf.drawString(42, y, "StudentHub — Student Report"); y -= 30
    pdf.setFont("Helvetica-Bold", 9); pdf.drawString(42, y, "ID"); pdf.drawString(110, y, "Name"); pdf.drawString(300, y, "Course"); pdf.drawString(470, y, "Status"); y -= 14
    pdf.setFont("Helvetica", 9)
    for row in rows:
        if y < 48: pdf.showPage(); y = height - 52; pdf.setFont("Helvetica", 9)
        pdf.drawString(42, y, row["student_id"]); pdf.drawString(110, y, row["name"][:30]); pdf.drawString(300, y, row["course"][:26]); pdf.drawString(470, y, row["status"]); y -= 16
    pdf.save(); output.seek(0)
    return Response(output.getvalue(), mimetype="application/pdf", headers={"Content-Disposition": "attachment; filename=studenthub-students.pdf"})


@app.get("/activity")
@roles_required("admin")
def activity():
    history = query_all("""SELECT h.*, COALESCE(u.full_name, 'System') AS user_name FROM activity_history h
                           LEFT JOIN users u ON u.id=h.user_id ORDER BY h.created_at DESC LIMIT 100""")
    return render_template("activity.html", history=history)


@app.get("/notifications")
@login_required
def notifications():
    user = current_user()
    notes = query_all("SELECT * FROM notifications WHERE recipient_role=%s ORDER BY created_at DESC LIMIT 50", (user["role"],))
    execute("UPDATE notifications SET is_read=TRUE WHERE recipient_role=%s", (user["role"],))
    return render_template("notifications.html", notifications=notes)


@app.route("/team", methods=["GET", "POST"])
@roles_required("admin")
def team():
    if request.method == "POST":
        username, full_name = request.form.get("username", "").strip(), request.form.get("full_name", "").strip()
        password, role = request.form.get("password", ""), request.form.get("role", "staff")
        if not username or not full_name or len(password) < 8:
            flash("Enter a username, full name, and password of at least 8 characters.", "error")
        else:
            try:
                execute("INSERT INTO users (username, password_hash, full_name, role) VALUES (%s, %s, %s, %s)", (username, generate_password_hash(password), full_name, role))
                flash("User account created.", "success")
            except Error:
                flash("That username is already in use.", "error")
        return redirect(url_for("team"))
    return render_template("team.html", users=query_all("SELECT id, username, full_name, role, created_at FROM users ORDER BY created_at DESC"))


@app.get("/about")
@login_required
def about():
    return render_template("about.html")


@app.errorhandler(413)
def file_too_large(_error):
    flash("Files must be 8 MB or smaller.", "error")
    return redirect(request.referrer or url_for("home"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
