from flask import Flask, jsonify, request, render_template
import sqlite3
import datetime
import pickle

app = Flask(__name__)

DB_PATH = "autism.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS child (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            age INTEGER,
            focus TEXT,
            face_encoding BLOB
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS session (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_id INTEGER,
            activity TEXT,
            xp INTEGER,
            created_at TEXT,
            FOREIGN KEY(child_id) REFERENCES child(id)
        )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def index():
    return render_template("index.html")


# ----- CHILD -----
@app.route("/api/children", methods=["GET"])
def list_children():
    conn = get_db()
    rows = conn.execute("SELECT id,name,age,focus FROM child").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/children", methods=["POST"])
def create_child():
    data = request.get_json()
    conn = get_db()
    conn.execute("INSERT INTO child(name,age,focus) VALUES(?,?,?)",
                 (data["name"], data["age"], data["focus"]))
    conn.commit()
    conn.close()
    return jsonify({"msg": "child added"})


# ----- SESSIONS -----
@app.route("/api/sessions", methods=["POST"])
def log_session():
    data = request.get_json()
    now = datetime.datetime.now().isoformat(timespec="seconds")

    conn = get_db()
    conn.execute("INSERT INTO session(child_id,activity,xp,created_at) VALUES(?,?,?,?)",
                 (data["child_id"], data["activity"], data["xp"], now))
    conn.commit()
    conn.close()
    return jsonify({"msg": "session stored"})


@app.route("/api/sessions/<int:child_id>")
def get_sessions(child_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT activity,xp,created_at FROM session WHERE child_id=? ORDER BY created_at DESC",
        (child_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/stats/<int:child_id>")
def get_stats(child_id):
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(SUM(xp),0) AS total_xp, COUNT(*) AS sessions "
        "FROM session WHERE child_id=?",
        (child_id,)
    ).fetchone()

    rows = conn.execute(
        "SELECT activity, COALESCE(SUM(xp),0) AS xp "
        "FROM session WHERE child_id=? GROUP BY activity",
        (child_id,)
    ).fetchall()

    conn.close()

    return jsonify({
        "total_xp": row["total_xp"],
        "sessions": row["sessions"],
        "per_activity": {r["activity"]: r["xp"] for r in rows}
    })


# ----- FACE REGISTER -----
@app.route("/api/face/register", methods=["POST"])
def register_face():
    data = request.get_json()
    child_id = data["child_id"]
    encoding = data["encoding"]

    enc_blob = pickle.dumps(encoding)

    conn = get_db()
    conn.execute("UPDATE child SET face_encoding=? WHERE id=?",
                 (enc_blob, child_id))
    conn.commit()
    conn.close()
    return jsonify({"msg": "face registered"})


# ----- FACE LOGIN -----
import face_recognition

@app.route("/api/face/login", methods=["POST"])
def face_login():
    data = request.get_json()
    encoding = data["encoding"]

    conn = get_db()
    rows = conn.execute("SELECT id,face_encoding FROM child WHERE face_encoding IS NOT NULL").fetchall()
    conn.close()

    for r in rows:
        stored = pickle.loads(r["face_encoding"])
        matches = face_recognition.compare_faces([stored], encoding)
        if matches[0]:
            return jsonify({"child_id": r["id"]})

    return jsonify({"child_id": None})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
