from __future__ import annotations
import os
from datetime import date, time, datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import streamlit as st
from snowflake.snowpark import Session
import tomllib  # Python 3.11 stdlib TOML reader

# Optional: key-pair auth. Only used if you set private_key_path in the creds file.
try:
    from cryptography.hazmat.primitives import serialization  # type: ignore
    from cryptography.hazmat.backends import default_backend  # type: ignore
    _CRYPTO_OK = True
except Exception:
    _CRYPTO_OK = False


session = None


def _default_cred_paths() -> list[Path]:
    """
    Search order for credentials file. First match wins.
    You can override with SNOWFLAKE_CRED_PATH=<full path>.
    """
    env = os.getenv("SNOWFLAKE_CRED_PATH")
    if env:
        return [Path(env)]

    here = Path.cwd()
    home = Path.home()

    return [
        here / "secrets" / "snowflake.toml",
        here / ".snowflake.toml",
        here / ".streamlit" / "snowflake.toml",
        home / ".config" / "snowflake" / "creds.toml",
        home / ".snowflake" / "creds.toml",
    ]

def _load_toml(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)

def _load_creds(profile: Optional[str] = None) -> tuple[dict, str]:
    """
    Load credentials dict and the profile name actually used.
    Supports multi-profile TOML.

    TOML shapes supported:

    1) Single profile:
        [connection]
        account = "xxx"
        user = "xxx"
        password = "xxx"
        role = "xxx"
        warehouse = "xxx"
        database = "xxx"
        schema = "xxx"
        authenticator = "snowflake"  # or "externalbrowser"

    2) Multi-profile:
        [dev]
        ...
        [prod]
        ...

    Select profile with SNOWFLAKE_PROFILE or argument.
    Default section tried: "connection", then "default".
    """
    paths = _default_cred_paths()
    for p in paths:
        if p.exists():
            data = _load_toml(p)
            prof = profile or os.getenv("SNOWFLAKE_PROFILE")
            if prof:
                if prof not in data:
                    raise FileNotFoundError(f"Profile '{prof}' not found in {p}")
                return data[prof], prof

            # No explicit profile: try common keys
            for key in ("connection", "default"):
                if key in data:
                    return data[key], key

            # If file is flat (no top-level tables), use it as-is
            if all(not isinstance(v, dict) for v in data.values()):
                return data, p.name

            raise ValueError(f"No usable profile found in {p}.")
    raise FileNotFoundError(
        "Snowflake credentials file not found. "
        "Set SNOWFLAKE_CRED_PATH or create secrets/snowflake.toml"
    )

def _maybe_load_private_key(path: str, passphrase: Optional[str]) -> Optional[bytes]:
    """
    Load a PKCS8 private key for key-pair auth. Returns the PEM bytes to pass to connector.
    Only used if private_key_path is specified in the creds file.
    """
    if not _CRYPTO_OK:
        raise RuntimeError(
            "cryptography is not installed. Remove private_key_path from creds "
            "or install cryptography locally."
        )
    p = Path(path).expanduser()
    key_bytes = p.read_bytes()
    password = passphrase.encode() if passphrase else None
    key = serialization.load_pem_private_key(key_bytes, password=password, backend=default_backend())
    # Snowflake connector expects the private key in DER bytes
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

def _in_sis() -> bool:
    """
    Heuristic: if we can import `get_active_session` and it returns a session, we're in SiS.
    """
    try:
        from snowflake.snowpark.context import get_active_session  # type: ignore
        s = get_active_session()
        _ = s.sql("SELECT 1").collect()
        return True
    except Exception:
        return False

def _create_local_session(creds: dict) -> Session:
    """
    Create a local Snowpark Session from creds dict.
    Supports password, externalbrowser, or key-pair.
    """
    cfg: Dict[str, Any] = {
        "account": creds.get("account"),
        "user": creds.get("user"),
        "role": creds.get("role"),
        "warehouse": creds.get("warehouse"),
        "database": creds.get("database"),
        "schema": creds.get("schema"),
    }

    # Auth modes
    if creds.get("authenticator", "snowflake").lower() == "externalbrowser":
        cfg["authenticator"] = "externalbrowser"
    elif "private_key_path" in creds:
        pk = _maybe_load_private_key(
            creds["private_key_path"],
            creds.get("private_key_passphrase"),
        )
        cfg["private_key"] = pk
    else:
        # default to password
        cfg["password"] = creds.get("password")

    # Optional params passthrough
    # e.g., region, account_identifier, session_parameters etc.
    if "session_parameters" in creds and isinstance(creds["session_parameters"], dict):
        cfg["session_parameters"] = creds["session_parameters"]

    return Session.builder.configs(cfg).create()

@st.cache_resource(show_spinner=False)
def get_session(profile: Optional[str] = None) -> Session:
    """
    One function to get a Snowpark session everywhere:
    - In SiS: returns the active session
    - Locally: reads creds file and creates a session

    Cached with st.cache_resource so it’s created once per app run.
    """
    if _in_sis():
        from snowflake.snowpark.context import get_active_session  # type: ignore
        return get_active_session()

    creds, prof_used = _load_creds(profile)
    return _create_local_session(creds)

@st.cache_data(ttl=60, show_spinner=False)
def read_sql(sql: str, params: dict | None = None, profile: Optional[str] = None):
    """
    Run a Snowflake (Snowpark) SQL and return a pandas DataFrame.
    Use Python .format() style with named params, e.g. {start} {end} {trader_id}.
    Dates/timestamps/strings are auto-quoted here; numbers pass as-is.
    Works in SiS and local Streamlit
    """
    # session = get_session(profile)
    global session

    if params:
        safe_params = {}
        for k, v in params.items():
            if v is None:
                safe_params[k] = None
            elif isinstance(v, (datetime, date, time, str)):
                safe_params[k] = f"'{v}'"
            else:
                safe_params[k] = v
        sql = sql.format(**safe_params)
        with st.expander('query:'):
            st.code(sql)

    try:
        return session.sql(sql).to_pandas()
    except:
        session = get_session(profile)
        return session.sql(sql).to_pandas()

def execute_sql(sql: str, *, profile: Optional[str] = None):
    """
    Non-cached helper for non-SELECT (use carefully).
    """
    session = get_session(profile)
    return session.sql(sql).collect()
