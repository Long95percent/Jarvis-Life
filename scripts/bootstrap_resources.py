import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download local AI resources and initialize a ShadowLink RAG index."
    )
    parser.add_argument(
        "--embedding-repo",
        default="intfloat/multilingual-e5-small",
        help="Hugging Face model repo used for local embeddings.",
    )
    parser.add_argument(
        "--model-dir",
        default="",
        help="Target directory for the downloaded embedding model. Defaults to models/<repo-name>.",
    )
    parser.add_argument(
        "--mode-id",
        default="default",
        help="ShadowLink task/mode id used as the rag_indexes/<mode-id> directory.",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="File or directory to index. Repeat this flag for multiple paths.",
    )
    parser.add_argument(
        "--extensions",
        default=".md,.txt,.py,.json",
        help="Comma-separated file extensions to index when a directory is provided.",
    )
    parser.add_argument(
        "--ollama-model",
        default="",
        help="Optional Ollama model name to pull locally, for example qwen2.5:7b.",
    )
    parser.add_argument(
        "--skip-model",
        action="store_true",
        help="Skip the Hugging Face embedding model download step.",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip the RAG index initialization step.",
    )
    return parser.parse_args()


def resolve_model_dir(args):
    if args.model_dir:
        return Path(args.model_dir).expanduser().resolve()
    repo_name = args.embedding_repo.rstrip("/").split("/")[-1]
    return PROJECT_ROOT / "models" / repo_name


def download_embedding_model(repo_id: str, target_dir: Path):
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'huggingface-hub'. Run: pip install -r requirements.txt"
        ) from exc

    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"[1/3] Downloading embedding model: {repo_id}")
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    print(f"Saved model to: {target_dir}")


def pull_ollama_model(model_name: str):
    if not model_name:
        return
    print(f"[2/3] Pulling Ollama model: {model_name}")
    try:
        subprocess.run(
            ["ollama", "pull", model_name],
            check=True,
            cwd=str(PROJECT_ROOT),
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "The 'ollama' command was not found. Install Ollama first or omit --ollama-model."
        ) from exc


def collect_documents(paths, extensions):
    normalized_exts = {
        ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
        for ext in extensions.split(",")
        if ext.strip()
    }
    documents = []
    seen = set()

    for raw_path in paths:
        current = Path(raw_path).expanduser().resolve()
        if not current.exists():
            print(f"Skip missing path: {current}")
            continue
        if current.is_file():
            if current.suffix.lower() in normalized_exts:
                add_document(documents, seen, current)
            continue
        for file_path in current.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in normalized_exts:
                add_document(documents, seen, file_path)
    return documents


def add_document(documents, seen, file_path: Path):
    key = str(file_path).lower()
    if key in seen:
        return
    seen.add(key)
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = file_path.read_text(encoding="gb18030", errors="ignore")
    except OSError:
        return
    if not text.strip():
        return
    documents.append(
        {
            "id": file_path.stem,
            "source": str(file_path),
            "text": text,
        }
    )


def build_index(mode_id: str, model_dir: Path, sources, extensions: str):
    from rag.rag_engine import RAGEngine

    documents = collect_documents(sources, extensions)
    if not documents:
        raise RuntimeError(
            "No documents were collected. Pass at least one valid --source path for index creation."
        )

    print(f"[3/3] Building index for mode_id='{mode_id}'")
    os.environ["SHADOWLINK_EMBEDDING_MODEL"] = str(model_dir)
    engine = RAGEngine(index_root=str(PROJECT_ROOT / "rag_indexes"), embedding_model_name=str(model_dir))
    engine.set_mode(mode_id)
    chunk_count = engine.ingest(documents, progress_callback=print)
    print(f"Indexed {len(documents)} documents into {PROJECT_ROOT / 'rag_indexes' / mode_id}")
    print(f"Generated chunks: {chunk_count}")


def main():
    args = parse_args()
    model_dir = resolve_model_dir(args)

    if not args.skip_model:
        download_embedding_model(args.embedding_repo, model_dir)

    if args.ollama_model:
        pull_ollama_model(args.ollama_model)

    if not args.skip_index:
        build_index(args.mode_id, model_dir, args.source, args.extensions)

    print("Bootstrap finished.")


if __name__ == "__main__":
    main()
