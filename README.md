 Task Manager App – Multi-User Boards with FastAPI, Firebase Auth, and Firestore

This cloud-based task management application allows users to collaborate on shared task boards with real-time updates, secure user authentication, and robust backend logic. It was developed using Python (FastAPI) for the backend, Firebase Authentication for login/logout, and Firestore as the NoSQL cloud database.

The project followed secure deployment practices by avoiding local service keys and interacting directly with Firestore using authorized API calls. 


 ✨ Key Features

Login/Logout via Firebase Authentication (JavaScript client)
Task Boards: Create and manage boards with nested tasks
Multi-User Collaboration: Invite users to boards and assign tasks
Task Management: Add, edit, complete, and delete tasks
Task Metadata: Tracks due dates, timestamps, and completion status
Firestore Hierarchy
  - Users → Boards → Tasks (no composite indexes required)
Strict Permissions:
    Only board owners can rename or delete boards or remove users
     Removed users no longer see the board and their tasks are unassigned
Dashboards:
    Counters for active, completed, and total tasks
    Highlighting for unassigned tasks

 What I Learned

 Designing multi-user systems with cloud Firestore
 Working with parent-child document relationships
 Managing authentication with Firebase and JavaScript
 Handling state updates and permission checks in FastAPI
 Securing project structure to avoid leaking sensitive files
 Writing maintainable, testable, and well-organized Python code


 Setup 

To run this locally (you’ll need your own Firebase project):
bash
uvicorn main:app --reload
