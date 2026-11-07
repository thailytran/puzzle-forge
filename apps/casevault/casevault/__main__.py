"""Server-side commands:  python -m casevault <command>

create-admin <username>          password prompt + prints the TOTP secret / otpauth URI (2FA)
import-etsy <orders.csv>         Etsy "Order Items" CSV -> known orders, re-check pending solves
import-coupons <coupons.csv>     Etsy coupon pool (percent,code,expires)
recheck                          re-check pending Etsy/Shopify orders once
worker                           loop: outbox every minute, pending re-check every 30 minutes
"""

from __future__ import annotations

import getpass
import sys
import time
from pathlib import Path

from sqlalchemy import insert

from casevault import db as T
from casevault.config import Settings
from casevault.providers import Providers
from casevault.security import hash_password, new_totp_secret, otpauth_uri
from casevault.service import Vault


def _vault() -> Vault:
    s = Settings.from_env()
    return Vault(s, T.make_engine(s.database_url), Providers.real(s))


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    v = _vault()
    if cmd == "create-admin":
        user = args[0]
        pw = getpass.getpass("Password (min 12 chars): ")
        if len(pw) < 12:
            print("password too short")
            return 1
        secret = new_totp_secret()
        with v.e.begin() as c:
            c.execute(
                insert(T.admins).values(
                    username=user, password_hash=hash_password(pw), totp_secret=secret
                )
            )
        print("Add this to Google Authenticator / Authy / 1Password (2FA):")
        print("  secret:", secret)
        print("  uri:   ", otpauth_uri(secret, user, v.s.site_name))
        return 0
    if cmd == "import-etsy":
        print(v.import_etsy_csv(Path(args[0]).read_text(encoding="utf-8-sig")))
    elif cmd == "import-coupons":
        print("imported", v.import_pool_csv(Path(args[0]).read_text(encoding="utf-8-sig")))
    elif cmd == "recheck":
        print(v.recheck_pending())
        print(v.process_outbox())
    elif cmd == "worker":
        last = 0.0
        while True:
            v.process_outbox()
            if time.time() - last > 1800:
                v.recheck_pending()
                last = time.time()
            time.sleep(60)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
