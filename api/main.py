"""
main.py — Outpace API Entrypoint
==================================
This is the starting point of our backend. When you run this file,
it starts a web server that listens for requests (e.g. "add a new
competitor", "get my briefs") and routes them to the right logic.

Think of this file as the front door of the house — it doesn't do
the actual work itself, it just directs traffic to the right room
(the routers).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# We'll build these router files next — they contain the actual
# logic for handling competitor and brief-related requests.
from api.routers import competitors, briefs


# Create the FastAPI application instance.
# This `app` object is what actually runs the server.
app = FastAPI(
    title="Outpace API",
    description="Backend API for Outpace — AI-powered competitive intelligence",
    version="0.1.0"
)


# ------------------------------------------------------------
# CORS (Cross-Origin Resource Sharing)
# ------------------------------------------------------------
# By default, browsers block a frontend running on one domain
# (e.g. localhost:3000) from talking to a backend on another
# domain (e.g. localhost:8000). This middleware tells the browser
# "it's okay, allow requests from these origins."
#
# For now we allow everything ("*") since we're in early development.
# Before going live, we'll lock this down to only our real frontend URL.
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # TODO: restrict this before production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# ROUTERS
# ------------------------------------------------------------
# A "router" is a group of related endpoints (URLs).
# Instead of putting every single endpoint in this one file
# (which would get messy fast), we organize them by feature:
#
#   - competitors.py -> endpoints for adding/viewing competitors
#   - briefs.py       -> endpoints for viewing generated briefs
#
# `prefix` means every URL in that router starts with that path.
# So an endpoint like "/list" inside competitors.py becomes
# accessible at "/competitors/list".
# ------------------------------------------------------------
app.include_router(competitors.router, prefix="/competitors", tags=["Competitors"])
app.include_router(briefs.router, prefix="/briefs", tags=["Briefs"])


# ------------------------------------------------------------
# HEALTH CHECK ENDPOINT
# ------------------------------------------------------------
# A simple endpoint to confirm the server is alive and running.
# Visiting "/" in your browser or hitting it with curl should
# return this message. Useful for debugging deployment issues later.
# ------------------------------------------------------------
@app.get("/")
def health_check():
    return {"status": "ok", "service": "outpace-api"}