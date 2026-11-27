from .demo_bench import seed_fixture
from .demo_reference import seed_references


def seed(conn):
    seed_fixture(conn)
    seed_references(conn)
