# scripts/ingest.py
import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent  # remonte de scripts/ à la racine du projet
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
# ------------------------------------------------------------------------

from app.services.vector_store import get_vector_store  

def ingest_knowledge(path: str) -> None:
    root = Path(path)
    if not root.exists():
        print(f"[INGEST] Path {root} does not exist.")
        return

    texts = []
    metadatas = []
    ids = []

    for idx, file in enumerate(root.glob("*.txt")):
        content = file.read_text(encoding="utf-8", errors="ignore")
        texts.append(content)
        metadatas.append({"filename": file.name})
        ids.append(str(idx))

    if not texts:
        print("[INGEST] No .txt files found.")
        return

    vs = get_vector_store()
    vs.add_documents(texts=texts, metadatas=metadatas, ids=ids)
    print(f"[INGEST] Ingested {len(texts)} documents.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=str, required=True, default="data/knowledge", help="Folder containing .txt files")
    args = parser.parse_args()
    ingest_knowledge(args.path)


if __name__ == "__main__":
    main()
