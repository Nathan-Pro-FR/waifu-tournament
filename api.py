import os
import secrets
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel, Field
import database as db

load_dotenv()

API_KEY = os.getenv("API_KEY", "").strip()

app = FastAPI(
    title="Waifu Tournament API",
    description="API officielle de synchronisation Waifu Tournament",
    version="1.0.0"
)


@app.on_event("startup")
def startup():
    db.init_db()


def require_api_key(
    authorization: Optional[str] = Header(default=None)
):

    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="API_KEY non configurée."
        )

    expected = f"Bearer {API_KEY}"

    if not authorization or not secrets.compare_digest(
        authorization,
        expected
    ):
        raise HTTPException(
            status_code=401,
            detail="Clé API invalide."
        )


class ParticipantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    image_url: Optional[str] = Field(
        default=None,
        max_length=500
    )


class DuelCreate(BaseModel):
    participant_a: str = Field(min_length=1, max_length=100)
    participant_b: str = Field(min_length=1, max_length=100)


class VoteCreate(BaseModel):
    participant_id: int
    user_id: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=1, max_length=150)


class StatusUpdate(BaseModel):
    status: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "waifu-tournament"
    }


@app.get(
    "/v1/participants",
    dependencies=[Depends(require_api_key)]
)
def participants():
    return db.list_participants()


@app.post(
    "/v1/participants",
    dependencies=[Depends(require_api_key)]
)
def propose_participant(payload: ParticipantCreate):

    try:
        return db.propose_participant(
            payload.name,
            payload.image_url
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc)
        )


@app.post(
    "/v1/participants/{participant_id}/approve",
    dependencies=[Depends(require_api_key)]
)
def approve_participant(participant_id: int):

    try:
        return db.approve_participant(participant_id)

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )


@app.get(
    "/v1/duels/current",
    dependencies=[Depends(require_api_key)]
)
def current_duel():
    return db.get_current_duel()


@app.get(
    "/v1/duels/{duel_id}",
    dependencies=[Depends(require_api_key)]
)
def get_duel(duel_id: int):

    result = db.get_duel(duel_id)

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Duel introuvable."
        )

    return result


@app.post(
    "/v1/duels",
    dependencies=[Depends(require_api_key)]
)
def create_duel(payload: DuelCreate):

    try:
        return db.create_duel(
            payload.participant_a,
            payload.participant_b
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


@app.patch(
    "/v1/duels/{duel_id}",
    dependencies=[Depends(require_api_key)]
)
def update_duel(
    duel_id: int,
    payload: StatusUpdate
):

    try:
        return db.set_duel_status(
            duel_id,
            payload.status
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


@app.post(
    "/v1/duels/{duel_id}/votes",
    dependencies=[Depends(require_api_key)]
)
def vote(
    duel_id: int,
    payload: VoteCreate
):

    try:
        return db.cast_vote(
            duel_id,
            payload.participant_id,
            payload.user_id,
            payload.username,
            "site"
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


@app.get(
    "/v1/duels/{duel_id}/results",
    dependencies=[Depends(require_api_key)]
)
def results(duel_id: int):

    try:
        return db.get_duel_results(duel_id)

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )


@app.get(
    "/v1/leaderboard",
    dependencies=[Depends(require_api_key)]
)
def leaderboard():
    return db.get_leaderboard()
