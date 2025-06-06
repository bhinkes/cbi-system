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
async def retrieve_data(ticker: str, scenario: str, metric: str, as_of_date: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Retrieve the most recent data - FIXED with proper timezone handling
    """
    
    # Clean inputs
    ticker = ticker.strip()
    scenario = scenario.lower().strip()
    metric = metric.strip()
    
    # Validate scenario early
    valid_scenarios = ["down", "base", "up"]
    if scenario not in valid_scenarios:
        raise HTTPException(status_code=400, detail=f"Invalid scenario: '{scenario}'")
    
    # Build query based on whether we have a date filter
    if as_of_date:
        try:
            # Parse the as_of_date
            as_of_datetime = datetime.strptime(as_of_date, "%Y-%m-%d")
            
            # Convert to NY timezone end of day
            ny_tz = pytz.timezone('America/New_York')
            
            # Handle both timezone-aware and naive datetimes
            if as_of_datetime.tzinfo is None:
                # If naive, localize to NY timezone
                end_of_day = ny_tz.localize(as_of_datetime.replace(hour=23, minute=59, second=59))
            else:
                # If already timezone-aware, convert to NY
                end_of_day = as_of_datetime.replace(hour=23, minute=59, second=59).astimezone(ny_tz)
            
            # Query with date filter - use raw SQL ordering to be absolutely sure
            latest_submission = db.query(models.Submission).filter(
                models.Submission.ticker == ticker,
                models.Submission.timestamp <= end_of_day
            ).order_by(
                models.Submission.id.desc()  # Use ID DESC as primary - highest ID = most recent insert
            ).first()
            
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        # No date filter - get absolutely most recent by ID (which correlates with insertion order)
        # Using ID DESC ensures we get the truly latest regardless of timezone issues
        latest_submission = db.query(models.Submission).filter(
            models.Submission.ticker == ticker
        ).order_by(
            models.Submission.id.desc()  # Highest ID = most recent insertion
        ).first()
    
    # Check if submission found
    if not latest_submission:
        # Get available tickers for error message
        all_tickers = db.query(models.Submission.ticker).distinct().all()
        available_tickers = [t[0] for t in all_tickers]
        
        date_msg = f" as of {as_of_date}" if as_of_date else ""
        raise HTTPException(
            status_code=404, 
            detail=f"No data found for ticker: '{ticker}'{date_msg}. Available tickers: {available_tickers}"
        )
    
    # Get the requested value
    value = None
    
    if metric == "Target Multiple":
        target_values = {
            "down": latest_submission.down_target_multiple,
            "base": latest_submission.base_target_multiple, 
            "up": latest_submission.up_target_multiple
        }
        value = target_values[scenario]
        
    elif metric == "Target Price":
        price_values = {
            "down": latest_submission.down_target_price,
            "base": latest_submission.base_target_price,
            "up": latest_submission.up_target_price
        }
        value = price_values[scenario]
        
    else:
        # Handle KPIs
        kpi = db.query(models.KPI).filter(
            models.KPI.submission_id == latest_submission.id,
            models.KPI.kpi_name == metric
        ).first()
        
        if not kpi:
            # Get all available KPIs for this submission
            available_kpis = db.query(models.KPI.kpi_name).filter(
                models.KPI.submission_id == latest_submission.id
            ).distinct().all()
            kpi_names = [kpi_name[0] for kpi_name in available_kpis]
            
            raise HTTPException(
                status_code=404, 
                detail=f"KPI '{metric}' not found for {ticker}. Available KPIs: {kpi_names}"
            )
        
        kpi_values = {
            "down": kpi.down_value,
            "base": kpi.base_value,
            "up": kpi.up_value
        }
        value = kpi_values[scenario]
    
    # Check if value exists and is not None
    if value is None:
        raise HTTPException(
            status_code=404, 
            detail=f"No {scenario} value found for '{metric}' in latest submission (ID: {latest_submission.id}) for ticker '{ticker}'"
        )
    
    # Return response with clear metadata
    return {
        "value": float(value),
        "ticker": ticker,
        "scenario": scenario, 
        "metric": metric,
        "submission_id": latest_submission.id,
        "timestamp": format_ny_time(latest_submission.timestamp),
        "username": latest_submission.username
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
