"""Stand-alone server for trying the parser with the frontend before app/main.py exists.

    cd backend
    uvicorn parser.dev_server:app --reload

Then run the Streamlit frontend; it talks to http://localhost:8000 by default.
Once app/main.py includes parser.router, this file isn't needed.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .router import router

app = FastAPI(title="Semester Sentinel parser")
# only needed for a browser frontend (the Streamlit app calls from the server side)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
