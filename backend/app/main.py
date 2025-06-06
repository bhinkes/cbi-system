from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import os
from datetime import datetime
from typing import Optional, List
import json
from pathlib import Path

from . import models, database

app = FastAPI(title="CBI System")

# Database setup
models.Base.metadata.create_all(bind=database.engine)

# Get the directory where main.py is located and find templates
# We're in /app/app/main.py, so we need to go up 2 levels to reach /app/
BASE_DIR = Path(__file__).parent.parent.parent
template_dir = BASE_DIR / "frontend" / "templates"
templates = Jinja2Templates(directory=str(template_dir))

# Mount static files only if directory exists
static_dir = BASE_DIR / "frontend" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Dependency to get DB session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == "BLH" and password == "CBI":
        response = RedirectResponse(url="/dashboard", status_code=302)
        return response
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    submissions = db.query(models.Submission).order_by(models.Submission.timestamp.desc()).limit(10).all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "submissions": submissions})

@app.post("/submit")
async def submit_data(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    
    # Create submission
    submission = models.Submission(
        ticker=data["ticker"],
        username=data["username"],
        down_target_multiple=data.get("down_target_multiple"),
        base_target_multiple=data.get("base_target_multiple"),
        up_target_multiple=data.get("up_target_multiple"),
        down_target_price=data.get("down_target_price"),
        base_target_price=data.get("base_target_price"),
        up_target_price=data.get("up_target_price")
    )
    
    db.add(submission)
    db.commit()
    db.refresh(submission)
    
    # Create KPIs
    for kpi in data.get("kpis", []):
        kpi_record = models.KPI(
            submission_id=submission.id,
            kpi_name=kpi["name"],
            down_value=kpi.get("down_value"),
            base_value=kpi.get("base_value"),
            up_value=kpi.get("up_value")
        )
        db.add(kpi_record)
    
    db.commit()
    
    return {"success": True, "message": "Data submitted successfully", "submission_id": submission.id}

@app.get("/retrieve")
async def retrieve_data(ticker: str, scenario: str, metric: str, db: Session = Depends(get_db)):
    # Get latest submission for ticker
    submission = db.query(models.Submission).filter(
        models.Submission.ticker == ticker
    ).order_by(models.Submission.timestamp.desc()).first()
    
    if not submission:
        raise HTTPException(status_code=404, detail="No data found")
    
    # Handle target multiples and prices
    if metric == "Target Multiple":
        if scenario == "down":
            value = submission.down_target_multiple
        elif scenario == "base":
            value = submission.base_target_multiple
        elif scenario == "up":
            value = submission.up_target_multiple
        else:
            raise HTTPException(status_code=400, detail="Invalid scenario")
    elif metric == "Target Price":
        if scenario == "down":
            value = submission.down_target_price
        elif scenario == "base":
            value = submission.base_target_price
        elif scenario == "up":
            value = submission.up_target_price
        else:
            raise HTTPException(status_code=400, detail="Invalid scenario")
    else:
        # Handle KPIs
        kpi = db.query(models.KPI).filter(
            models.KPI.submission_id == submission.id,
            models.KPI.kpi_name == metric
        ).first()
        
        if not kpi:
            raise HTTPException(status_code=404, detail="KPI not found")
        
        if scenario == "down":
            value = kpi.down_value
        elif scenario == "base":
            value = kpi.base_value
        elif scenario == "up":
            value = kpi.up_value
        else:
            raise HTTPException(status_code=400, detail="Invalid scenario")
    
    if value is None:
        raise HTTPException(status_code=404, detail="No data found")
    
    return {"value": float(value), "timestamp": submission.timestamp}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
