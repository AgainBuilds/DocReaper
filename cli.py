import asyncio, json
from pathlib import Path
import typer
from .storage import Store
from .service import Engine
from .discovery import discover_sitemap, discover_oai_pmh

app = typer.Typer(help="Academic Identity Engine command line")

def get_engine(db: str): return Engine(Store(db))

@app.command()
def ingest_text(path: Path, title: str = typer.Option(None), db: str = "sqlite:///./aie.db"):
    result = get_engine(db).ingest_text(path.read_text(encoding="utf-8"), title=title or path.name, source_name="cli", raw=path.read_bytes())
    typer.echo(json.dumps({"id": result["document"]["id"], "duplicate_of": result["duplicate_of"]}, indent=2))

@app.command()
def discover_sitemap_cmd(url: str, max_urls: int = 1000, db: str = "sqlite:///./aie.db"):
    store = Store(db)
    records = asyncio.run(discover_sitemap(url, max_urls))
    for r in records: store.add_discovery(r["url"], r["title"], r["source"], r["metadata"])
    typer.echo(f"Saved {len(records)} discovered URLs")

@app.command()
def discover_oai(url: str, set_spec: str = typer.Option(None, "--set"), max_records: int = 1000, db: str = "sqlite:///./aie.db"):
    store = Store(db)
    records = asyncio.run(discover_oai_pmh(url, set_spec, max_records))
    for r in records: store.add_discovery(r["url"], r["title"], r["source"], r["metadata"])
    typer.echo(f"Saved {len(records)} discovered records")

@app.command()
def stats(db: str = "sqlite:///./aie.db"):
    typer.echo(json.dumps(Store(db).stats(), indent=2))

if __name__ == "__main__": app()
