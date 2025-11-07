import pytest
from models import init_db, engine, Base, db


@pytest.fixture(scope='session')
def setup_db():
    init_db('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    yield
    try:
        db.session.remove()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def session(setup_db):
    # Each test gets a fresh transactional scope
    connection = engine.connect()
    transaction = connection.begin()

    options = dict(bind=connection, binds={})
    sess = db.session.registry()

    db.session = sess
    yield sess

    try:
        transaction.rollback()
    except Exception:
        pass
    try:
        connection.close()
    except Exception:
        pass
    try:
        sess.remove()
    except Exception:
        pass
