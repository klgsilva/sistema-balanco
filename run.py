import os
from pathlib import Path

from app import create_app


app = create_app()


if __name__ == "__main__":
    cert_path = Path("work/cert.pem")
    key_path = Path("work/key.pem")
    usar_https = os.environ.get("USE_HTTPS") == "1"
    ssl_context = (str(cert_path), str(key_path)) if usar_https and cert_path.exists() and key_path.exists() else None
    port = int(os.environ.get("PORT", "5001"))
    app.run(debug=False, host="0.0.0.0", port=port, ssl_context=ssl_context, use_reloader=False)
