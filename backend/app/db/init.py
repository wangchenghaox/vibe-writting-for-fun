from app.db.base import Base, engine


def init_db(bind=None):
    from app.models import novel  # noqa: F401

    Base.metadata.create_all(bind=bind or engine)
