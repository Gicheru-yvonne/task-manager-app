import os
import requests
from fastapi import FastAPI, Request, Form, Header, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi import Body
from datetime import datetime

FIREBASE_API_KEY = "AIzaSyCuglc7ZGBb6ICnqsOg9pVeojNhgythB8k"
PROJECT_ID = "assignment-2-c9bd8"
FIRESTORE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def verify_token(authorization: str = Header(None)):
    if not authorization or "Bearer " not in authorization:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    token = authorization.replace("Bearer ", "").strip()
    verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_API_KEY}"
    response = requests.post(verify_url, json={"idToken": token})
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return response.json()

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("main.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    token = request.cookies.get("token")
    if token:
        verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_API_KEY}"
        verify_response = requests.post(verify_url, json={"idToken": token})
        user_info = verify_response.json()
        if "users" in user_info:
            return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/main", response_class=HTMLResponse)
async def main_page(request: Request):
    return templates.TemplateResponse("main.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/my_boards")
async def get_my_boards(request: Request):
    token = request.cookies.get("token")
    if not token:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})

    verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_API_KEY}"
    user_info = requests.post(verify_url, json={"idToken": token}).json()
    uid = user_info.get("users", [{}])[0].get("localId", "")

    r = requests.get(f"{FIRESTORE_URL}/taskboards")
    boards = []
    try:
        for doc in r.json().get("documents", []):
            fields = doc.get("fields", {})
            doc_id = doc["name"].split("/")[-1]
            owner = fields.get("owner", {}).get("stringValue", "")
            members = fields.get("members", {}).get("arrayValue", {}).get("values", [])

            member_ids = [m.get("stringValue", "") for m in members]
            if uid == owner or uid in member_ids:
                boards.append({
                    "id": doc_id,
                    "title": fields.get("title", {}).get("stringValue", ""),
                    "owner": owner
                })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    return {"boards": boards}

@app.get("/board/{board_id}", response_class=HTMLResponse)
async def view_board(request: Request, board_id: str):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_API_KEY}"
    verify_response = requests.post(verify_url, json={"idToken": token})
    user_info = verify_response.json()

    if "users" not in user_info:
        return RedirectResponse("/login", status_code=302)

    uid = user_info["users"][0]["localId"]

    r = requests.get(f"{FIRESTORE_URL}/taskboards/{board_id}")
    if r.status_code != 200:
        return JSONResponse(status_code=404, content={"error": "Taskboard not found"})

    board_data = r.json()
    fields = board_data.get("fields", {})

    owner = fields.get("owner", {}).get("stringValue", "")
    members = fields.get("members", {}).get("arrayValue", {}).get("values", [])
    member_ids = [m.get("stringValue", "") for m in members]

    if uid != owner and uid not in member_ids:
        return JSONResponse(status_code=403, content={"error": "You are not allowed to view this taskboard"})

    return templates.TemplateResponse("view_board.html", {
        "request": request,
        "board_id": board_id,
        "title": fields.get("title", {}).get("stringValue", "")
    })

@app.post("/board/{board_id}/add_task")
async def add_task(request: Request, board_id: str, task_title: str = Form(...), due_date: str = Form(...)):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    # Firestore format
    data = {
        "fields": {
            "board_id": {"stringValue": board_id},
            "title": {"stringValue": task_title},
            "due_date": {"stringValue": due_date},
            "complete": {"booleanValue": False}
        }
    }

    res = requests.post(f"{FIRESTORE_URL}/tasks", json=data)
    if res.status_code == 200:
        return RedirectResponse(f"/board/{board_id}", status_code=302)
    return JSONResponse(status_code=500, content={"error": "Failed to add task"})

@app.get("/board/{board_id}/tasks")
async def fetch_tasks(request: Request, board_id: str):
    token = request.cookies.get("token")
    if not token:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})

    r = requests.get(f"{FIRESTORE_URL}/tasks")
    tasks = []
    try:
        for doc in r.json().get("documents", []):
            fields = doc.get("fields", {})
            if fields.get("board_id", {}).get("stringValue", "") == board_id:
                tasks.append({
    "id": doc["name"].split("/")[-1],
    "title": fields.get("title", {}).get("stringValue", ""),
    "due_date": fields.get("due_date", {}).get("stringValue", ""),
    "complete": fields.get("complete", {}).get("booleanValue", False),
    "completed_at": fields.get("completed_at", {}).get("timestampValue", None)
})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    return {"tasks": tasks}

@app.post("/board/{board_id}/update_task/{task_id}")
async def update_task_completion(request: Request, board_id: str, task_id: str, complete: str = Form(...)):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    is_complete = complete.lower() == "true"
    
    # Always update the 'complete' field
    update_fields = {
        "complete": {"booleanValue": is_complete}
    }

    # If completed, add timestamp
    if is_complete:
        timestamp = datetime.utcnow().isoformat() + "Z"  # ISO format for Firestore
        update_fields["completed_at"] = {"timestampValue": timestamp}
    else:
        update_fields["completed_at"] = {"nullValue": None}  # Clear timestamp if unchecked

    update_data = {"fields": update_fields}
    patch_url = f"{FIRESTORE_URL}/tasks/{task_id}?updateMask.fieldPaths=complete&updateMask.fieldPaths=completed_at"
    
    response = requests.patch(patch_url, json=update_data)
    if response.status_code == 200:
        return RedirectResponse(f"/board/{board_id}", status_code=302)
    return JSONResponse(status_code=500, content={"error": "Failed to update task"})

@app.post("/board/{board_id}/edit_task/{task_id}")
async def edit_task(request: Request, board_id: str, task_id: str, new_title: str = Form(...), new_due_date: str = Form(...)):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    update_data = {
        "fields": {
            "title": {"stringValue": new_title},
            "due_date": {"stringValue": new_due_date}
        }
    }

    patch_url = f"{FIRESTORE_URL}/tasks/{task_id}?updateMask.fieldPaths=title&updateMask.fieldPaths=due_date"
    res = requests.patch(patch_url, json=update_data)

    if res.status_code == 200:
        return RedirectResponse(f"/board/{board_id}", status_code=302)
    return JSONResponse(status_code=500, content={"error": "Failed to update task"})


@app.post("/board/{board_id}/delete_task/{task_id}")
async def delete_task(request: Request, board_id: str, task_id: str):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    delete_url = f"{FIRESTORE_URL}/tasks/{task_id}"
    res = requests.delete(delete_url)

    if res.status_code == 200:
        return RedirectResponse(f"/board/{board_id}", status_code=302)
    return JSONResponse(status_code=500, content={"error": "Failed to delete task"})


@app.post("/create_board")
async def create_board(request: Request, board_name: str = Form(...)):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

   
    verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_API_KEY}"
    verify_response = requests.post(verify_url, json={"idToken": token})
    user_info = verify_response.json()

    if "users" not in user_info or not user_info["users"]:
        return JSONResponse(status_code=403, content={"error": "Invalid or expired token"})

    uid = user_info["users"][0].get("localId", "")
    if not uid:
        return JSONResponse(status_code=403, content={"error": "UID not found in token"})

    
    data = {
        "fields": {
            "title": {"stringValue": board_name},
            "owner": {"stringValue": uid},
            "members": {
                "arrayValue": {
                    "values": [{"stringValue": uid}]
                }
            }
        }
    }

    
    response = requests.post(f"{FIRESTORE_URL}/taskboards", json=data)
    if response.status_code == 200:
        return RedirectResponse("/dashboard", status_code=302)
    return JSONResponse(status_code=500, content={"error": "Failed to create task board"})

@app.post("/board/{board_id}/invite")
async def invite_user(request: Request, board_id: str, user_email: str = Form(...)):
    token = request.cookies.get("token")
    if not token:
        return RedirectResponse("/login", status_code=302)

    
    verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_API_KEY}"
    user_info = requests.post(verify_url, json={"idToken": token}).json()
    if "users" not in user_info:
        return RedirectResponse("/login", status_code=302)

    current_uid = user_info["users"][0]["localId"]

    
    board_res = requests.get(f"{FIRESTORE_URL}/taskboards/{board_id}")
    board_data = board_res.json()
    board_owner = board_data.get("fields", {}).get("owner", {}).get("stringValue", "")
    if current_uid != board_owner:
        return JSONResponse(status_code=403, content={"error": "Only the board owner can invite users"})

    
    users_res = requests.get(f"{FIRESTORE_URL}/users")
    user_docs = users_res.json().get("documents", [])
    invited_uid = ""
    for doc in user_docs:
        fields = doc.get("fields", {})
        if fields.get("email", {}).get("stringValue", "") == user_email:
            invited_uid = fields.get("uid", {}).get("stringValue", "")
            break

    if not invited_uid:
        return JSONResponse(status_code=404, content={"error": "User not found"})

    
    members = board_data.get("fields", {}).get("members", {}).get("arrayValue", {}).get("values", [])
    current_uids = [m.get("stringValue", "") for m in members]

    if invited_uid in current_uids:
        return JSONResponse(content={"message": "User already a member"})

    current_uids.append(invited_uid)
    update_data = {
        "fields": {
            "members": {
                "arrayValue": {
                    "values": [{"stringValue": uid} for uid in current_uids]
                }
            }
        }
    }

    patch_url = f"{FIRESTORE_URL}/taskboards/{board_id}?updateMask.fieldPaths=members"
    patch_response = requests.patch(patch_url, json=update_data)

    if patch_response.status_code == 200:
        return RedirectResponse(f"/board/{board_id}", status_code=302)
    else:
        return JSONResponse(status_code=500, content={"error": "Failed to update members"})

@app.post("/save_user")
async def save_user(request: Request, payload: dict = Body(...), authorization: str = Header(None)):
    user_info = verify_token(authorization)
    uid = user_info["users"][0]["localId"]
    email = payload.get("email")

    if not email:
        return JSONResponse(status_code=400, content={"error": "Email required"})

    user_data = {
        "fields": {
            "email": {"stringValue": email},
            "uid": {"stringValue": uid}
        }
    }

    res = requests.post(f"{FIRESTORE_URL}/users", json=user_data)
    if res.status_code == 200:
        return {"message": "User saved"}
    return JSONResponse(status_code=500, content={"error": "Failed to save user"})