from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import desc
import os
from datetime import datetime
import pytz
from typing import Optional, List
import json
from pathlib import Path

from . import models, database

app = FastAPI(title="CBI System")

# Database setup
models.Base.metadata.create_all(bind=database.engine)

# Get the directory where main.py is located and find templates
BASE_DIR = Path(__file__).parent.parent
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

# Helper function to format timestamp to NY time
def format_ny_time(timestamp):
    if timestamp.tzinfo is None:
        # If timestamp is naive, assume it's UTC and convert to NY
        timestamp = pytz.UTC.localize(timestamp)
    ny_tz = pytz.timezone('America/New_York')
    ny_time = timestamp.astimezone(ny_tz)
    return ny_time.strftime('%Y-%m-%d %H:%M:%S %Z')

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
    # Get all submissions with their KPIs, ordered by most recent
    submissions = db.query(models.Submission).order_by(desc(models.Submission.timestamp)).limit(20).all()
    
    # Prepare enhanced data for dashboard
    enhanced_submissions = []
    for submission in submissions:
        # Get all KPIs for this submission
        kpis_dict = {}
        for kpi in submission.kpis:
            kpis_dict[kpi.kpi_name] = {
                'down': float(kpi.down_value) if kpi.down_value else None,
                'base': float(kpi.base_value) if kpi.base_value else None,
                'up': float(kpi.up_value) if kpi.up_value else None
            }
        
        # Format the submission data
        enhanced_submission = {
            'id': submission.id,
            'ticker': submission.ticker,
            'username': submission.username,
            'timestamp': format_ny_time(submission.timestamp),
            'down_target_multiple': float(submission.down_target_multiple) if submission.down_target_multiple else None,
            'base_target_multiple': float(submission.base_target_multiple) if submission.base_target_multiple else None,
            'up_target_multiple': float(submission.up_target_multiple) if submission.up_target_multiple else None,
            'down_target_price': float(submission.down_target_price) if submission.down_target_price else None,
            'base_target_price': float(submission.base_target_price) if submission.base_target_price else None,
            'up_target_price': float(submission.up_target_price) if submission.up_target_price else None,
            'kpis': kpis_dict
        }
        enhanced_submissions.append(enhanced_submission)
    
    # Get summary stats
    total_submissions = db.query(models.Submission).count()
    unique_tickers = db.query(models.Submission.ticker).distinct().count()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "submissions": enhanced_submissions,
        "total_submissions": total_submissions,
        "unique_tickers": unique_tickers
    })

@app.get("/data", response_class=HTMLResponse)
async def data_view(request: Request, db: Session = Depends(get_db)):
    # Get all submissions with full details
    submissions = db.query(models.Submission).order_by(desc(models.Submission.timestamp)).all()
    
    # Prepare detailed data for data view
    detailed_submissions = []
    for submission in submissions:
        # Get all KPIs for this submission
        kpis_dict = {}
        for kpi in submission.kpis:
            kpis_dict[kpi.kpi_name] = {
                'down': float(kpi.down_value) if kpi.down_value else None,
                'base': float(kpi.base_value) if kpi.base_value else None,
                'up': float(kpi.up_value) if kpi.up_value else None
            }
        
        detailed_submission = {
            'id': submission.id,
            'ticker': submission.ticker,
            'username': submission.username,
            'timestamp': format_ny_time(submission.timestamp),
            'down_target_multiple': float(submission.down_target_multiple) if submission.down_target_multiple else None,
            'base_target_multiple': float(submission.base_target_multiple) if submission.base_target_multiple else None,
            'up_target_multiple': float(submission.up_target_multiple) if submission.up_target_multiple else None,
            'down_target_price': float(submission.down_target_price) if submission.down_target_price else None,
            'base_target_price': float(submission.base_target_price) if submission.base_target_price else None,
            'up_target_price': float(submission.up_target_price) if submission.up_target_price else None,
            'kpis': kpis_dict
        }
        detailed_submissions.append(detailed_submission)
    
    return templates.TemplateResponse("data.html", {
        "request": request, 
        "submissions": detailed_submissions
    })

@app.post("/submit")
async def submit_data(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    
    # Get current NY time
    ny_tz = pytz.timezone('America/New_York')
    current_time = datetime.now(ny_tz)
    
    # Create submission
    submission = models.Submission(
        ticker=data["ticker"],
        username=data["username"],
        timestamp=current_time,
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
    ).order_by(desc(models.Submission.timestamp)).first()
    
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
    
    return {"value": float(value), "timestamp": format_ny_time(submission.timestamp)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
