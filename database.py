import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from sqlalchemy import (
    create_engine,
    String,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    select,
    func
)

from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker
)

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./waifu_tournament.db"
)

connect_args = (
    {"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


class Participant(Base):

    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    approved: Mapped[bool] = mapped_column(
        default=False,
        nullable=False
    )

    proposer_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    proposer_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class Duel(Base):

    __tablename__ = "duels"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    participant_a_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id"),
        nullable=False
    )

    participant_b_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id"),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "participant_a_id != participant_b_id"
        ),
        CheckConstraint(
            "status IN ('draft', 'open', 'closed')"
        )
    )


class Vote(Base):

    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    duel_id: Mapped[int] = mapped_column(
        ForeignKey("duels.id", ondelete="CASCADE"),
        nullable=False
    )

    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id"),
        nullable=False
    )

    user_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    username: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    source: Mapped[str] = mapped_column(
        String(20),
        default="site",
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint(
            "duel_id",
            "user_id",
            name="one_vote_per_user_per_duel"
        ),
    )


def init_db():
    Base.metadata.create_all(engine)


def participant_dict(p):
    return {
        "id": p.id,
        "name": p.name,
        "image_url": p.image_url,
        "approved": p.approved
    }


def duel_dict(session, duel):

    a = session.get(
        Participant,
        duel.participant_a_id
    )

    b = session.get(
        Participant,
        duel.participant_b_id
    )

    count = session.scalar(
        select(func.count(Vote.id)).where(
            Vote.duel_id == duel.id
        )
    ) or 0

    return {
        "id": duel.id,
        "status": duel.status,
        "participant_a": participant_dict(a),
        "participant_b": participant_dict(b),
        "vote_count": count,
        "created_at": duel.created_at.isoformat(),
        "opened_at": (
            duel.opened_at.isoformat()
            if duel.opened_at else None
        ),
        "closed_at": (
            duel.closed_at.isoformat()
            if duel.closed_at else None
        )
    }


def list_participants(approved_only=True):

    with SessionLocal() as session:

        query = select(Participant)

        if approved_only:
            query = query.where(
                Participant.approved.is_(True)
            )

        query = query.order_by(Participant.name)

        return [
            participant_dict(p)
            for p in session.scalars(query).all()
        ]


def propose_participant(
    name,
    image_url=None,
    proposer_id=None,
    proposer_name=None
):

    name = (name or "").strip()

    if not name or len(name) > 100:
        raise ValueError("Nom invalide.")

    if image_url and (
        not image_url.startswith("https://")
        or len(image_url) > 500
    ):
        raise ValueError("URL d'image HTTPS invalide.")

    with SessionLocal.begin() as session:

        existing = session.scalar(
            select(Participant).where(
                func.lower(Participant.name) == name.lower()
            )
        )

        if existing:
            raise ValueError("Personnage déjà existant.")

        p = Participant(
            name=name,
            image_url=image_url,
            approved=False,
            proposer_id=proposer_id,
            proposer_name=proposer_name
        )

        session.add(p)
        session.flush()

        return participant_dict(p)


def approve_participant(participant_id):

    with SessionLocal.begin() as session:

        p = session.get(Participant, participant_id)

        if not p:
            raise LookupError("Personnage introuvable.")

        p.approved = True

        return participant_dict(p)


def get_or_create_approved(session, name):

    name = (name or "").strip()

    if not name or len(name) > 100:
        raise ValueError("Nom invalide.")

    p = session.scalar(
        select(Participant).where(
            func.lower(Participant.name) == name.lower()
        )
    )

    if p:

        if not p.approved:
            raise ValueError(
                f"{name} n'a pas encore été approuvé."
            )

        return p

    p = Participant(
        name=name,
        approved=True
    )

    session.add(p)
    session.flush()

    return p


def create_duel(name_a, name_b):

    if name_a.strip().lower() == name_b.strip().lower():
        raise ValueError("Deux personnages différents sont requis.")

    with SessionLocal.begin() as session:

        a = get_or_create_approved(session, name_a)
        b = get_or_create_approved(session, name_b)

        duel = Duel(
            participant_a_id=a.id,
            participant_b_id=b.id,
            status="draft"
        )

        session.add(duel)
        session.flush()

        return duel_dict(session, duel)


def get_duel(duel_id):

    with SessionLocal() as session:

        duel = session.get(Duel, duel_id)

        return (
            duel_dict(session, duel)
            if duel else None
        )


def get_current_duel():

    with SessionLocal() as session:

        duel = session.scalar(
            select(Duel)
            .where(Duel.status == "open")
            .order_by(Duel.opened_at.desc(), Duel.id.desc())
        )

        return (
            duel_dict(session, duel)
            if duel else None
        )


def list_open_duels():

    with SessionLocal() as session:

        duels = session.scalars(
            select(Duel).where(Duel.status == "open")
        ).all()

        return [
            duel_dict(session, duel)
            for duel in duels
        ]


def set_duel_status(duel_id, status):

    if status not in {"open", "closed"}:
        raise ValueError("Statut invalide.")

    with SessionLocal.begin() as session:

        duel = session.get(Duel, duel_id)

        if not duel:
            raise LookupError("Duel introuvable.")

        if status == "open":

            if duel.status == "closed":
                raise ValueError(
                    "Impossible de rouvrir un duel clôturé."
                )

            duel.status = "open"
            duel.opened_at = datetime.now(timezone.utc)

        else:

            if duel.status != "open":
                raise ValueError(
                    "Le duel n'est pas ouvert."
                )

            duel.status = "closed"
            duel.closed_at = datetime.now(timezone.utc)

        session.flush()

        return duel_dict(session, duel)


def cast_vote(
    duel_id,
    participant_id,
    user_id,
    username,
    source="site"
):

    with SessionLocal.begin() as session:

        duel = session.get(Duel, duel_id)

        if not duel:
            raise LookupError("Duel introuvable.")

        if duel.status != "open":
            raise ValueError("Les votes sont fermés.")

        if participant_id not in {
            duel.participant_a_id,
            duel.participant_b_id
        }:
            raise ValueError("Participant absent du duel.")

        participant = session.get(
            Participant,
            participant_id
        )

        vote = session.scalar(
            select(Vote).where(
                Vote.duel_id == duel_id,
                Vote.user_id == str(user_id)
            )
        )

        changed = (
            vote is not None
            and vote.participant_id != participant_id
        )

        if vote:

            vote.participant_id = participant_id
            vote.username = str(username)[:150]
            vote.source = source
            vote.updated_at = datetime.now(timezone.utc)

        else:

            vote = Vote(
                duel_id=duel_id,
                participant_id=participant_id,
                user_id=str(user_id),
                username=str(username)[:150],
                source=source
            )

            session.add(vote)

        session.flush()

        count = session.scalar(
            select(func.count(Vote.id)).where(
                Vote.duel_id == duel_id
            )
        ) or 0

        return {
            "duel_id": duel_id,
            "participant_id": participant_id,
            "participant_name": participant.name,
            "vote_count": count,
            "changed": changed
        }


def get_leaderboard():

    with SessionLocal() as session:

        query = (
            select(
                Participant,
                func.count(Vote.id).label("votes")
            )
            .outerjoin(
                Vote,
                Vote.participant_id == Participant.id
            )
            .where(Participant.approved.is_(True))
            .group_by(Participant.id)
            .order_by(
                func.count(Vote.id).desc(),
                Participant.name.asc()
            )
        )

        return [
            {
                "id": p.id,
                "name": p.name,
                "votes": votes
            }
            for p, votes in session.execute(query).all()
        ]


def get_duel_results(duel_id):

    with SessionLocal() as session:

        duel = session.get(Duel, duel_id)

        if not duel:
            raise LookupError("Duel introuvable.")

        query = (
            select(
                Vote.participant_id,
                func.count(Vote.id)
            )
            .where(Vote.duel_id == duel_id)
            .group_by(Vote.participant_id)
        )

        counts = dict(session.execute(query).all())

        return {
            "duel_id": duel_id,
            "participant_a": participant_dict(
                session.get(Participant, duel.participant_a_id)
            ),
            "participant_b": participant_dict(
                session.get(Participant, duel.participant_b_id)
            ),
            "votes_a": counts.get(duel.participant_a_id, 0),
            "votes_b": counts.get(duel.participant_b_id, 0),
            "total": sum(counts.values()),
            "status": duel.status
        }
