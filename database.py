import sqlite3
from flask import g
import os

DATABASE = 'placement_portal.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.executescript('''
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS company (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            hr_contact TEXT,
            website TEXT,
            industry TEXT,
            description TEXT,
            approval_status TEXT DEFAULT "pending",
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS student (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT,
            branch TEXT,
            cgpa REAL,
            graduation_year INTEGER,
            skills TEXT,
            bio TEXT,
            resume_path TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS placement_drive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            job_title TEXT NOT NULL,
            job_description TEXT,
            eligibility_criteria TEXT,
            application_deadline DATE,
            salary TEXT,
            location TEXT,
            status TEXT DEFAULT "pending",
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES company(id)
        );

        CREATE TABLE IF NOT EXISTS application (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            drive_id INTEGER NOT NULL,
            application_date DATE,
            status TEXT DEFAULT "applied",
            FOREIGN KEY (student_id) REFERENCES student(id),
            FOREIGN KEY (drive_id) REFERENCES placement_drive(id),
            UNIQUE(student_id, drive_id)
        );
    ''')

    # Seed admin if not exists
    existing_admin = c.execute('SELECT id FROM admin WHERE email="admin@institute.edu"').fetchone()
    if not existing_admin:
        c.execute('INSERT INTO admin (name, email, password) VALUES (?, ?, ?)',
                  ('Institute Admin', 'admin@institute.edu', 'admin123'))

    conn.commit()
    conn.close()
    print("Database initialized.")
