from scraper.postgres_db import _connection_kwargs


def test_connection_kwargs_decodes_supabase_pooler_url_password() -> None:
    kwargs = _connection_kwargs(
        "postgresql://postgres.example:pass%40123@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"
    )

    assert kwargs == {
        "host": "aws-1-eu-central-1.pooler.supabase.com",
        "port": 5432,
        "dbname": "postgres",
        "user": "postgres.example",
        "password": "pass@123",
    }
