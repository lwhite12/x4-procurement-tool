# data/ (the extracted/compiled X4 game data) is gitignored -- see
# .gitignore's own comment -- but Docker's build context is the local
# filesystem, not git, so `fly deploy`/`docker build` still picks it up
# from disk and bakes it into the image. Nothing else needs to fetch it at
# deploy time; it's baked in read-only, matching how api.py already uses
# it (query-only, never written to at request-serving time).
FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY data/ data/
COPY VERSION .

# Matches how this app is run everywhere else in this project (README/
# local dev) -- `python src/api.py` adds src/'s own directory to sys.path,
# which is what lets api.py's sibling imports (e.g.
# "from summarize_production import ...") resolve without a package
# structure or WORKDIR trick.
CMD ["python", "src/api.py"]
