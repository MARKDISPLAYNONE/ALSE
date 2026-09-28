import pytest

from data.settings import validate_supabase_url


def test_good():
    assert validate_supabase_url("https://abcdefghijklmnopqrst.supabase.co/") == "https://abcdefghijklmnopqrst.supabase.co"

@pytest.mark.parametrize("bad", [
    "https://supabase.com/dashboard/project/abcdefghijklmnopqrst",
    "https://abcdefghijklmnopqrst.supabase.co/rest/v1",
    "http://abcdefghijklmnopqrst.supabase.co",
])
def test_bad(bad):
    with pytest.raises(RuntimeError):
        validate_supabase_url(bad)
