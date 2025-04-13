from fastapi import FastAPI, Request, Form, Header, HTTPException, Body
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from datetime import datetime
from google.cloud import firestore
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests


db = firestore.Client()
firebase_request_adapter = google_requests.Request()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def verify_token(request: Request = None, token: str = None):
    if request:
        token = request.cookies.get("token")
        print("🔥 Token from cookie:", token)
    elif token:
        print("🔥 Token from header:", token)
    else:
        raise HTTPException(status_code=401, detail="No token provided")

    try:
        decoded = id_token.verify_firebase_token(token, firebase_request_adapter)


        print("✅ Token decoded:", decoded)
        return decoded
    except Exception as e:
        print("❌ Token verification failed:", e)
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("main.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    token = request.cookies.get("token")
    if token:
        try:
            id_token.verify_oauth2_token(token, firebase_request_adapter)
            return RedirectResponse("/dashboard", status_code=302)
        except Exception:
            pass
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/auth/login")
async def login_user(idToken: str = Form(...)):
    try:
        id_token.verify_oauth2_token(idToken, firebase_request_adapter)
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(key="token", value=idToken, httponly=True)
        return response
    except Exception:
        return JSONResponse(status_code=401, content={"error": "Invalid token"})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.post("/create_board")
async def create_board(request: Request, board_name: str = Form(...)):
    try:
        decoded = verify_token(request)
    except HTTPException:
        return RedirectResponse("/login", status_code=302)

    uid = decoded.get("sub")  # ✅ correct user ID key


    board_ref = db.collection("taskboards").document()
    board_data = {
        "id": board_ref.id,
        "title": board_name,
        "created_by": uid,
        "member_ids": [uid],
        "created_at": firestore.SERVER_TIMESTAMP
    }

    board_ref.set(board_data)
    return RedirectResponse("/dashboard", status_code=302)



@app.get("/my_boards")
async def get_my_boards(request: Request):
    try:
        decoded = verify_token(request)
    except HTTPException:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})

    uid = decoded.get("sub")

    boards_query = db.collection("taskboards").where("member_ids", "array_contains", uid).stream()

    boards = []
    for doc in boards_query:
        board = doc.to_dict()
        board["is_creator"] = board.get("created_by") == uid  
        boards.append(board)

    return {"boards": boards}




@app.get("/board/{board_id}", response_class=HTMLResponse)
async def view_board(request: Request, board_id: str):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    decoded = id_token.verify_firebase_token(token, firebase_request_adapter)
    uid = decoded.get("sub")  # Use "sub" for Firebase UID

    doc = db.collection("taskboards").document(board_id).get()
    if not doc.exists:
        return JSONResponse(status_code=404, content={"error": "Taskboard not found"})

    board = doc.to_dict()

    if uid != board.get("created_by") and uid not in board.get("member_ids", []):
        return JSONResponse(status_code=403, content={"error": "Not authorized"})

    title = board.get("title") or "Untitled Board"

    return templates.TemplateResponse("view_board.html", {
        "request": request,
        "board_id": board_id,
        "title": title
    })



@app.get("/board/{board_id}/tasks")
async def fetch_tasks(request: Request, board_id: str):
    token = request.cookies.get("token")
    if not token:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})
    tasks = []
    for task in db.collection("tasks").where("board_id", "==", board_id).stream():
        t = task.to_dict()
        t["id"] = task.id
        tasks.append(t)
    return {"tasks": tasks}

@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("token")
    return response

@app.post("/board/{board_id}/add_task")
async def add_task(request: Request, board_id: str, task_title: str = Form(...), due_date: str = Form(...)):
    try:
        decoded = verify_token(request)
    except Exception:
        return RedirectResponse("/login", status_code=302)

    uid = decoded.get("sub")  



    task_data = {
    "board_id": board_id,
    "title": task_title,
    "due_date": due_date,
    "complete": False,
    "assigned_to": [str(uid)]  
}


    db.collection("tasks").add(task_data)
    return RedirectResponse(f"/board/{board_id}", status_code=302)


@app.post("/save_user")
async def save_user(request: Request, payload: dict = Body(...), authorization: str = Header(None)):
    print("📥 Raw Authorization Header:", authorization)

    token = authorization.split(" ")[1] if authorization and authorization.startswith("Bearer ") else None
    if not token:
        return JSONResponse(status_code=401, content={"error": "Missing or malformed token"})

    print("🔑 Extracted Token:", token[:30], "...")

    try:
        decoded = verify_token(token=token)
    except Exception as e:
        print("❌ Token verification failed:", e)
        return JSONResponse(status_code=401, content={"error": "Invalid token"})

    
    uid = decoded.get("uid") or decoded.get("user_id")
    email = payload.get("email")

    if not uid or not email:
        return JSONResponse(status_code=400, content={"error": "UID and email are required"})

    
    db.collection("users").document(uid).set({
        "uid": uid,
        "email": email
    })

    print("✅ Saved user to Firestore:", {"uid": uid, "email": email})
    return {"message": "User saved"}






@app.post("/board/{board_id}/update_task/{task_id}")
async def update_task_completion(
    request: Request,
    board_id: str,
    task_id: str,
    complete: str = Form(...)
):
    try:
        decoded = verify_token(request)
    except Exception:
        return RedirectResponse("/login", status_code=302)

    is_complete = complete.lower() == "true"
    task_ref = db.collection("tasks").document(task_id)

    update_data = {
        "complete": is_complete,
        "completed_at": datetime.utcnow() if is_complete else None
    }

    task_ref.update(update_data)

    return RedirectResponse(f"/board/{board_id}", status_code=302)

@app.post("/board/{board_id}/edit_task/{task_id}")
async def edit_task(
    request: Request,
    board_id: str,
    task_id: str,
    new_title: str = Form(...),
    new_due_date: str = Form(...),
    assigned_to_uid: str = Form(None)  # ✅ Optional new field
):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    try:
        decoded = verify_token(request)
    except Exception:
        return RedirectResponse("/login", status_code=302)

    task_ref = db.collection("tasks").document(task_id)

    update_data = {
        "title": new_title,
        "due_date": new_due_date,
    }

    if assigned_to_uid:
        update_data["assigned_to"] = [assigned_to_uid]
        update_data["was_unassigned"] = False  # ✅ Clear red highlight

    task_ref.update(update_data)

    return RedirectResponse(f"/board/{board_id}", status_code=302)




@app.post("/board/{board_id}/delete_task/{task_id}")
async def delete_task(request: Request, board_id: str, task_id: str):
    try:
        decoded = verify_token(request)  
    except Exception:
        return RedirectResponse("/login", status_code=302)

    task_ref = db.collection("tasks").document(task_id)
    task_ref.delete()

    return RedirectResponse(f"/board/{board_id}", status_code=302)



@app.post("/board/{board_id}/invite")
async def invite_user(request: Request, board_id: str, user_email: str = Form(...)):
    try:
        decoded = verify_token(request)
        print("✅ Token decoded for invite:", decoded)
    except Exception as e:
        print("🚨 Invite token verification error:", e)
        return RedirectResponse("/login", status_code=302)

    current_uid = decoded.get("sub")  # ✅ consistent with other routes

    board_ref = db.collection("taskboards").document(board_id)
    board_doc = board_ref.get()
    if not board_doc.exists:
        return JSONResponse(status_code=404, content={"error": "Board not found"})

    board_data = board_doc.to_dict()
    if board_data["created_by"] != current_uid:  
        return JSONResponse(status_code=403, content={"error": "Only the owner can invite users"})

    # Find user by email
    user_docs = db.collection("users").where("email", "==", user_email).stream()
    invited_uid = None
    for doc in user_docs:
        invited_uid = doc.id  
        break

    if not invited_uid:
        return JSONResponse(status_code=404, content={"error": "User not found"})

    current_members = board_data.get("member_ids", [])
    if invited_uid in current_members:
        return JSONResponse(content={"message": "User already a member"})

    current_members.append(invited_uid)
    board_ref.update({"member_ids": current_members})

    print(f"✅ Invited UID {invited_uid} added to board {board_id}")
    return RedirectResponse(f"/board/{board_id}", status_code=302)


@app.post("/board/{board_id}/rename")
async def rename_board(request: Request, board_id: str, new_title: str = Form(...)):
    try:
        decoded = verify_token(request)  
    except Exception:
        return RedirectResponse("/login", status_code=302)

    current_uid = decoded.get("sub")  

    board_ref = db.collection("taskboards").document(board_id)
    board_doc = board_ref.get()
    if not board_doc.exists:
        return JSONResponse(status_code=404, content={"error": "Board not found"})

    board_data = board_doc.to_dict()
    if board_data["created_by"] != current_uid: 
        return JSONResponse(status_code=403, content={"error": "Only the owner can rename the board"})

    board_ref.update({"title": new_title})
    return RedirectResponse(f"/board/{board_id}", status_code=302)


@app.post("/board/{board_id}/remove_user")
async def remove_user_from_board(request: Request, board_id: str, user_email: str = Form(...)):
    try:
        decoded = verify_token(request)
    except Exception:
        return RedirectResponse("/login", status_code=302)

    current_uid = decoded.get("sub")

    board_ref = db.collection("taskboards").document(board_id)
    board_doc = board_ref.get()
    if not board_doc.exists:
        return JSONResponse(status_code=404, content={"error": "Board not found"})

    board = board_doc.to_dict()

    if board["created_by"] != current_uid:
        return JSONResponse(status_code=403, content={"error": "Only the owner can remove users"})

    
    user_query = db.collection("users").where("email", "==", user_email).stream()
    removed_uid = None
    for doc in user_query:
        removed_uid = doc.id
        break

    if not removed_uid:
        return JSONResponse(status_code=404, content={"error": "User not found"})

    
    updated_members = board.get("member_ids", [])
    if removed_uid in updated_members:
        updated_members.remove(removed_uid)
        board_ref.update({"member_ids": updated_members})

        
        tasks_query = db.collection("tasks").where("board_id", "==", board_id).stream()
        for task_doc in tasks_query:
            task = task_doc.to_dict()
            if removed_uid in task.get("assigned_to", []):
                new_assignees = [uid for uid in task["assigned_to"] if uid != removed_uid]
                db.collection("tasks").document(task_doc.id).update({
                    "assigned_to": new_assignees,
                    "was_unassigned": True  # 🟥 highlight in frontend
                })

    return RedirectResponse(f"/board/{board_id}", status_code=302)
