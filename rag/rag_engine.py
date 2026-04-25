import os
import json
import hashlib
from datetime import datetime
import urllib.request
import urllib.error
import sqlite3
import time


class WorkflowResourcesPlugin:
    def __init__(self, tasks_config_path="tasks_config.json"):
        self.tasks_config_path = tasks_config_path

    def collect_documents(self, mode_id: str):
        mode_id = (mode_id or "").strip()
        if not mode_id:
            return []
        tasks = self._load_tasks()
        task = None
        for t in tasks:
            if isinstance(t, dict) and t.get("mode_id") == mode_id:
                task = t
                break
        if not task:
            return []

        paths = task.get("repo_paths", task.get("paths", []))
        if not isinstance(paths, list):
            paths = []
        files = self._collect_files(paths)
        docs = []
        for fp in files:
            text = self._read_text(fp)
            if not text:
                continue
            docs.append({"id": self._sha1(fp), "source": fp, "text": text})
        return docs

    def signature(self, mode_id: str):
        mode_id = (mode_id or "").strip()
        if not mode_id:
            return {"mode_id": "", "files": []}
        tasks = self._load_tasks()
        task = None
        for t in tasks:
            if isinstance(t, dict) and t.get("mode_id") == mode_id:
                task = t
                break
        if not task:
            return {"mode_id": mode_id, "files": []}

        paths = task.get("repo_paths", task.get("paths", []))
        if not isinstance(paths, list):
            paths = []
        files = self._collect_files(paths)
        out = []
        for fp in files:
            try:
                st = os.stat(fp)
                out.append({"path": fp, "mtime": int(st.st_mtime), "size": int(st.st_size)})
            except Exception:
                continue
        out.sort(key=lambda x: x["path"].lower())
        return {"mode_id": mode_id, "files": out}

    def _load_tasks(self):
        try:
            if os.path.exists(self.tasks_config_path):
                with open(self.tasks_config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except Exception:
            return []
        return []

    def _collect_files(self, paths):
        out = []
        for p in paths or []:
            p2 = (p or "").strip()
            if not p2:
                continue
            if p2.startswith(("http://", "https://")):
                from rag.web_crawler import WebCrawlerPlugin
                crawler = WebCrawlerPlugin()
                cached_path = crawler.crawl(p2)
                if cached_path:
                    out.append(cached_path)
                continue
            if p2.startswith("obsidian://"):
                continue
            if p2.startswith("file:///"):
                p2 = p2[8:]
            p2 = p2.replace("/", os.sep)
            if os.path.isdir(p2):
                for root, _, files in os.walk(p2):
                    for fn in files:
                        if fn.lower().endswith((".txt", ".md")):
                            out.append(os.path.join(root, fn))
                continue
            if os.path.isfile(p2) and p2.lower().endswith((".txt", ".md")):
                out.append(p2)
        dedup = []
        seen = set()
        for fp in out:
            key = fp.lower()
            if key in seen:
                continue
            seen.add(key)
            dedup.append(fp)
        return dedup

    def _read_text(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            try:
                with open(path, "r", encoding="gb18030", errors="ignore") as f:
                    return f.read()
            except Exception:
                return ""

    def _sha1(self, s):
        return hashlib.sha1((s or "").encode("utf-8", errors="ignore")).hexdigest()
class ChatHistoryPlugin:
    def __init__(self, db_path="chat_history.db"):
        self.db_path = db_path

    def collect_documents(self, mode_id: str):
        from storage.history_manager import HistoryManager
        hm = HistoryManager(self.db_path)
        messages = hm.get_all_messages_for_mode(mode_id)
        if not messages:
            return []
        
        # Group messages by session
        sessions = {}
        for m in messages:
            sid = m["session_id"]
            if sid not in sessions:
                sessions[sid] = []
            sessions[sid].append(m)
            
        docs = []
        for sid, msgs in sessions.items():
            session_info = hm.get_session_by_id(sid)
            title = session_info["title"] if session_info else "Session"
            text_lines = [f"Chat History: {title}"]
            for m in msgs:
                role = "User" if m["role"] == "user" else "Agent"
                text_lines.append(f"{role}: {m['content']}")
            
            text = "\n\n".join(text_lines)
            docs.append({
                "id": sid,
                "source": f"History: {title}",
                "text": text
            })
            
        # Also collect from history_archives
        archive_dir = os.path.join("rag_indexes", mode_id, "history_archives")
        if os.path.exists(archive_dir):
            for f in os.listdir(archive_dir):
                if f.endswith(".md"):
                    filepath = os.path.join(archive_dir, f)
                    try:
                        with open(filepath, "r", encoding="utf-8") as file:
                            text = file.read()
                            docs.append({
                                "id": f,
                                "source": f"Archive: {f}",
                                "text": text
                            })
                    except Exception:
                        pass

        return docs

class RAGEngine:
    def __init__(
        self,
        index_root="rag_indexes",
        #BAAI/bge-small-zh-v1.5是什么，有什么讲究吗
        embedding_model_name="BAAI/bge-small-zh-v1.5",
        #chunk_size 是每个文档的最大字符数，chunk_overlap 是每个文档之间的重叠字符数
        chunk_size=800,
        chunk_overlap=120,
        cache_dir=None,
        hf_endpoint=None,
        network_probe_timeout_s=2,
        faiss_index_type="auto",
        faiss_ivf_nlist=64,
        faiss_hnsw_m=32,
        embedding_cache=True,
    ):
        self.index_root = index_root
        env_model = os.environ.get("SHADOWLINK_EMBEDDING_MODEL", "").strip()
        if env_model:
            self.embedding_model_name = env_model
        else:
            project_root = os.path.dirname(os.path.dirname(__file__))
            local_default = os.path.join(project_root, "models", "multilingual-e5-small")
            self.embedding_model_name = local_default if os.path.isdir(local_default) else embedding_model_name
        self.chunk_size = int(chunk_size)
        self.chunk_overlap = int(chunk_overlap)
        self.cache_dir = cache_dir
        self.hf_endpoint = hf_endpoint
        self.network_probe_timeout_s = int(network_probe_timeout_s)
        self.faiss_index_type = os.environ.get("SHADOWLINK_FAISS_INDEX_TYPE", str(faiss_index_type or "auto")).strip().lower()
        self.faiss_ivf_nlist = int(os.environ.get("SHADOWLINK_FAISS_IVF_NLIST", str(faiss_ivf_nlist)))
        self.faiss_hnsw_m = int(os.environ.get("SHADOWLINK_FAISS_HNSW_M", str(faiss_hnsw_m)))
        self.embedding_cache = bool(int(os.environ.get("SHADOWLINK_EMBEDDING_CACHE", "1"))) if embedding_cache else False

        self.mode_id = None
        self.mode_dir = None
        self._index = None
        self._docstore = []
        self._embedder = None
        self._dim = None
        self._cache_conn = None
    #set_mode 设置索引模式
    def set_mode(self, mode_id, subdir=""):
        mode_id = (mode_id or "").strip()
        if not mode_id:
            raise ValueError("mode_id is empty")
        
        self.mode_id = mode_id
        if subdir:
            self.mode_dir = os.path.join(self.index_root, mode_id, subdir)
        else:
            self.mode_dir = os.path.join(self.index_root, mode_id)
            
        os.makedirs(self.mode_dir, exist_ok=True)

        self._load()

    def clear(self):
        self._index = None
        self._docstore = []
        self._dim = None
        if self._cache_conn is not None:
            try:
                self._cache_conn.close()
            except Exception:
                pass
        self._cache_conn = None

    #ingest 索引文档
    def ingest(self, documents, cancel_check=None, progress_callback=None):
        if self.mode_dir is None:
            raise RuntimeError("set_mode() must be called before ingest()")
        docs = documents or []
        if not isinstance(docs, list):
            raise TypeError("documents must be a list")
        chunks = []
        
        for i, d in enumerate(docs):
            if cancel_check and cancel_check():
                return -1
            if not isinstance(d, dict):
                continue
            text = (d.get("text") or "").strip()
            if not text:
                continue
            source = (d.get("source") or "").strip()
            
            if progress_callback:
                progress_callback(f"Chunking: {os.path.basename(source)} ({i+1}/{len(docs)})")
                
            doc_id = (d.get("id") or source or self._sha1(text)[:12]).strip()
            for start, end, part in self._split_text(text):
                chunk_id = self._sha1("%s|%s|%s|%s" % (doc_id, source, start, part))
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "source": source,
                        "start": start,
                        "end": end,
                        "text": part,
                    }
                )

        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        
        import numpy as _np
        batch_size = 16
        all_vectors = []
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        for i in range(0, len(texts), batch_size):
            if cancel_check and cancel_check():
                return -1
            
            batch_num = (i // batch_size) + 1
            if progress_callback:
                progress_callback(f"Embedding: Batch {batch_num}/{total_batches} ({len(texts)} total chunks)")
                
            batch_texts = texts[i:i+batch_size]
            batch_vecs = self._embed(batch_texts)
            all_vectors.append(batch_vecs)

        if cancel_check and cancel_check():
            return -1

        if progress_callback:
            progress_callback(f"Saving index to disk...")

        vectors = _np.vstack(all_vectors)
        self._ensure_index(vectors.shape[1], n_vectors_expected=int(vectors.shape[0]))

        if hasattr(self._index, "is_trained") and not self._index.is_trained:
            if progress_callback:
                progress_callback("Training FAISS index (IVF)...")
            self._index.train(vectors)

        vectors = _np.asarray(vectors, dtype="float32")
        self._index.add(vectors)
        self._docstore.extend(chunks)
        self._save()
        return len(chunks)
    #retrieve 检索文档
    def retrieve(self, query, top_k=5):
        if self.mode_dir is None:
            raise RuntimeError("set_mode() must be called before retrieve()")
        q = (query or "").strip()
        if not q:
            return []
        if self._index is None or len(self._docstore) == 0:
            return []

        vec = self._embed([q])
        results = self._search(vec, int(top_k))
        out = []
        for score, idx in results:
            if idx < 0 or idx >= len(self._docstore):
                continue
            item = dict(self._docstore[idx])
            item["score"] = float(score)
            out.append(item)
        return out
    #build_context_prompt 构建上下文提示
    def build_context_prompt(self, query, chunks, budget_chars=2000, top_k=None):
        q = (query or "").strip()
        items = list(chunks or [])
        if top_k is not None:
            items = items[: int(top_k)]
        items = [c for c in items if isinstance(c, dict) and (c.get("text") or "").strip()]

        budget = int(budget_chars)
        parts = []
        used = 0
        for i, c in enumerate(items, 1):
            source = (c.get("source") or c.get("doc_id") or "").strip()
            text = (c.get("text") or "").strip()
            header = "[%d] %s\n" % (i, source)
            body = text + "\n"
            block = header + body
            if used + len(block) > budget:
                remain = max(0, budget - used - len(header) - 1)
                if remain <= 0:
                    break
                body2 = (text[:remain] + "…\n") if len(text) > remain else body
                block = header + body2
                parts.append(block)
                used += len(block)
                break
            parts.append(block)
            used += len(block)

        context = "".join(parts).strip()
        if context:
            return "Context (Top-K):\n%s\n\nQuestion:\n%s" % (context, q)
        return "Question:\n%s" % q
    #_ensure_deps 确保依赖项
    def _ensure_deps(self):
        missing = []
        try:
            import sentence_transformers  # noqa: F401
        except Exception:
            missing.append("sentence-transformers")
        try:
            import faiss  # noqa: F401
        except Exception:
            missing.append("faiss-cpu")
        if missing:
            msg = "Missing dependencies: %s" % (", ".join(missing))
            msg += "\nInstall (recommended, conda): conda install -c conda-forge faiss-cpu"
            msg += "\nInstall (pip): python -m pip install sentence-transformers"
            raise RuntimeError(msg)
    #_get_embedder 获取嵌入模型
    def _get_embedder(self):
        if self._embedder is not None:
            return self._embedder
        self._ensure_deps()
        from sentence_transformers import SentenceTransformer

        model_name = (self.embedding_model_name or "").strip()
        if not model_name:
            raise RuntimeError("embedding_model_name is empty")

        if self.hf_endpoint:
            os.environ["HF_ENDPOINT"] = self.hf_endpoint

        if os.path.isdir(model_name):
            self._validate_local_model_dir(model_name)
            local_only = True
        else:
            self._probe_hf(model_name)
            local_only = False

        kwargs = {}
        if local_only:
            # Prevent hanging on network requests when using local model directory
            kwargs["local_files_only"] = True
        if self.cache_dir:
            kwargs["cache_folder"] = self.cache_dir

        self._embedder = SentenceTransformer(model_name, **kwargs)
        return self._embedder
    #_embed 文本嵌入
    def _embed(self, texts):
        if not texts:
            return []
        if not self.embedding_cache or self.mode_dir is None:
            model = self._get_embedder()
            return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

        import numpy as _np
        model_name = (self.embedding_model_name or "").strip()
        conn = self._get_cache_conn()
        keys = [self._embed_key(model_name, t) for t in texts]

        cached = {}
        try:
            cur = conn.cursor()
            placeholders = ",".join(["?"] * len(keys))
            cur.execute(f"SELECT k, dim, vec FROM embeddings WHERE k IN ({placeholders})", keys)
            for k, dim, blob in cur.fetchall():
                if blob is None or dim is None:
                    continue
                cached[k] = _np.frombuffer(blob, dtype="float32", count=int(dim))
        except Exception:
            cached = {}

        missing_idx = []
        missing_texts = []
        for i, k in enumerate(keys):
            if k not in cached:
                missing_idx.append(i)
                missing_texts.append(texts[i])

        if missing_texts:
            model = self._get_embedder()
            vec_missing = model.encode(missing_texts, normalize_embeddings=True, show_progress_bar=False)
            vec_missing = _np.asarray(vec_missing, dtype="float32")
            now = int(time.time())
            try:
                cur = conn.cursor()
                for j, i in enumerate(missing_idx):
                    k = keys[i]
                    v = _np.asarray(vec_missing[j], dtype="float32").reshape(-1)
                    cur.execute(
                        "INSERT OR REPLACE INTO embeddings (k, dim, vec, updated_at) VALUES (?, ?, ?, ?)",
                        (k, int(v.shape[0]), v.tobytes(), now),
                    )
                conn.commit()
            except Exception:
                pass
            for j, i in enumerate(missing_idx):
                cached[keys[i]] = _np.asarray(vec_missing[j], dtype="float32").reshape(-1)

        ordered = _np.vstack([cached[k] for k in keys])
        return ordered
    #_ensure_index 确保索引
    def _ensure_index(self, dim, n_vectors_expected: int = 0):
        if self._index is not None:
            if self._dim is not None and int(self._dim) != int(dim):
                raise RuntimeError("Embedding dim mismatch: %s != %s" % (self._dim, dim))
            return
        self._ensure_deps()
        import faiss

        self._dim = int(dim)
        idx_type = self._choose_faiss_index_type(int(n_vectors_expected))
        if idx_type == "ivf":
            nlist = max(1, int(self.faiss_ivf_nlist))
            quantizer = faiss.IndexFlatIP(self._dim)
            index = faiss.IndexIVFFlat(quantizer, self._dim, nlist, faiss.METRIC_INNER_PRODUCT)
            index.nprobe = min(16, nlist)
            self._index = index
            return
        if idx_type == "hnsw":
            m = max(4, int(self.faiss_hnsw_m))
            try:
                index = faiss.IndexHNSWFlat(self._dim, m, faiss.METRIC_INNER_PRODUCT)
            except Exception:
                index = faiss.IndexHNSWFlat(self._dim, m)
                try:
                    index.metric_type = faiss.METRIC_INNER_PRODUCT
                except Exception:
                    pass
            try:
                index.hnsw.efSearch = 64
                index.hnsw.efConstruction = 200
            except Exception:
                pass
            self._index = index
            return
        self._index = faiss.IndexFlatIP(self._dim)
    #_search 索引搜索
    def _search(self, vector, top_k):
        import numpy as _np
        import faiss

        v = _np.asarray(vector, dtype="float32")
        if len(v.shape) == 1:
            v = v.reshape(1, -1)
        scores, indices = self._index.search(v, top_k)
        out = []
        for s, i in zip(scores[0].tolist(), indices[0].tolist()):
            out.append((s, i))
        return out
    #_paths 获取索引路径
    def _paths(self):
        index_path = os.path.join(self.mode_dir, "faiss.index")
        store_path = os.path.join(self.mode_dir, "docstore.json")
        manifest_path = os.path.join(self.mode_dir, "manifest.json")
        return index_path, store_path, manifest_path
    #_load 加载索引
    def _load(self):
        index_path, store_path, manifest_path = self._paths()
        self._index = None
        self._docstore = []
        self._dim = None

        if os.path.exists(store_path):
            try:
                with open(store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._docstore = data
            except Exception:
                self._docstore = []

        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    m = json.load(f)
                    self._dim = int(m.get("embedding_dim")) if m.get("embedding_dim") is not None else None
            except Exception:
                pass

        if os.path.exists(index_path):
            self._ensure_deps()
            import faiss

            try:
                self._index = faiss.read_index(index_path)
                if self._dim is None:
                    self._dim = int(self._index.d)
            except Exception:
                self._index = None
    #_save 保存索引
    def _save(self):
        index_path, store_path, manifest_path = self._paths()
        os.makedirs(self.mode_dir, exist_ok=True)
        if self._index is not None:
            self._ensure_deps()
            import faiss

            faiss.write_index(self._index, index_path)

        with open(store_path, "w", encoding="utf-8") as f:
            json.dump(self._docstore, f, ensure_ascii=False, indent=2)

        manifest = {
            "mode_id": self.mode_id,
            "embedding_model": self.embedding_model_name,
            "embedding_dim": self._dim,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "faiss_index_type": self.faiss_index_type,
            "faiss_ivf_nlist": self.faiss_ivf_nlist,
            "faiss_hnsw_m": self.faiss_hnsw_m,
            "embedding_cache": self.embedding_cache,
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "docstore_count": len(self._docstore),
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    #_split_text 文本分块
    def _split_text(self, text):
        t = (text or "").strip()
        if not t:
            return []
        size = max(50, int(self.chunk_size))
        overlap = max(0, min(int(self.chunk_overlap), size - 1))
        out = []
        start = 0
        n = len(t)
        while start < n:
            end = min(n, start + size)
            part = t[start:end].strip()
            if part:
                out.append((start, end, part))
            if end >= n:
                break
            start = end - overlap
        return out

    def _probe_hf(self, model_name: str):
        base = os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")
        url = "%s/%s/resolve/main/config.json" % (base, model_name)
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=self.network_probe_timeout_s):
                return
        except Exception:
            raise RuntimeError(
                "Cannot access embedding model '%s' from '%s'.\n"
                "Fix options:\n"
                "1) Download the model to a local folder and set embedding_model_name to that folder path.\n"
                "2) Configure a reachable HuggingFace endpoint mirror via hf_endpoint (e.g. https://hf-mirror.com) or environment HF_ENDPOINT.\n"
                "3) Check proxy / network connectivity.\n"
                % (model_name, base)
            )

    def _validate_local_model_dir(self, path: str):
        missing = []
        if not os.path.exists(os.path.join(path, "config.json")):
            missing.append("config.json")
        weights_ok = os.path.exists(os.path.join(path, "model.safetensors")) or os.path.exists(os.path.join(path, "pytorch_model.bin"))
        if not weights_ok:
            missing.append("model.safetensors or pytorch_model.bin")
        tok_ok = (
            os.path.exists(os.path.join(path, "tokenizer.json"))
            or os.path.exists(os.path.join(path, "vocab.txt"))
            or os.path.exists(os.path.join(path, "sentencepiece.bpe.model"))
        )
        if not tok_ok:
            missing.append("tokenizer.json or vocab.txt or sentencepiece.bpe.model")
        if missing:
            raise RuntimeError(
                "Local embedding model folder is missing required files:\n- %s\nFolder: %s"
                % ("\n- ".join(missing), path)
            )
    #_sha1 计算SHA1哈希
    def _sha1(self, s):
        return hashlib.sha1((s or "").encode("utf-8", errors="ignore")).hexdigest()

    def _embed_key(self, model_name: str, text: str) -> str:
        return self._sha1("%s|%s" % ((model_name or "").strip(), (text or "")))

    def _cache_db_path(self) -> str:
        return os.path.join(self.mode_dir, "embedding_cache.sqlite")

    def _get_cache_conn(self):
        if self._cache_conn is not None:
            return self._cache_conn
        os.makedirs(self.mode_dir, exist_ok=True)
        path = self._cache_db_path()
        conn = sqlite3.connect(path, timeout=2.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass
        conn.execute(
            "CREATE TABLE IF NOT EXISTS embeddings (k TEXT PRIMARY KEY, dim INTEGER, vec BLOB, updated_at INTEGER)"
        )
        self._cache_conn = conn
        return conn

    def _choose_faiss_index_type(self, n_vectors_expected: int) -> str:
        t = (self.faiss_index_type or "auto").strip().lower()
        if t in ("flat", "ivf", "hnsw"):
            return t
        n = int(n_vectors_expected or 0)
        if n >= 50000:
            return "hnsw"
        if n >= 5000:
            return "ivf"
        return "flat"
