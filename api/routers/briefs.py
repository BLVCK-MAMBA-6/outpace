"""
briefs.py — Brief Retrieval Endpoints
========================================
This router will handle fetching AI-synthesized briefs for a user
(the "here's what changed with your competitors" insights).

Currently a stub — we'll build this out once the diffing and
synthesis pipeline (Week 2-3) is actually producing real briefs
to fetch.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_briefs():
    """
    Placeholder endpoint. Will eventually return all briefs
    for the logged-in user, most recent first.
    """
    return {"message": "Briefs endpoint — coming in Week 2-3 once synthesis pipeline exists"}