"""Admin service for corpus ingestion, seeding and agent graph views.

Endpoints served:
    POST /admin/ingest            - Re-ingest the synthetic corpus into Chroma (202)
    POST /admin/seed              - Load asset model, HAZOP and users from data/
    GET  /agents/{agent_name}/graph - Mermaid view of a LangGraph graph (development only)
"""
import logging
import uuid
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import asyncpg
from config.settings import env
from app.agents.visualization import render_graph_html
from app.engines.corpus import load_corpus
from app.models.document_chunk_model import DocumentChunk
from app.models.document_model import Document
from app.models.enums import DataOrigin, DocType
from app.repositories.asset_repository import AssetRepository
from app.repositories.citation_repository import CitationRepository
from app.repositories.document_asset_repository import DocumentAssetRepository
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.replay_run_repository import ReplayRunRepository
from app.schemas.auth_schema import CurrentUser
from app.services import chroma_store
from app.services.replay_runtime import RUNNING, replay_manager
from app.services.retrieval_index import retrieval_index
from app.utils.response import response_error, response_success

logger = logging.getLogger(__name__)

# Namespace for deterministic vector ids (doc, revision, index, content hash)
POINT_NAMESPACE = uuid.UUID("5a1e100b-0000-4000-8000-00000000c0de")
SEED_COUNT_TABLES = (
    "sites", "units", "process_nodes", "assets", "asset_links", "sensor_tags",
    "safeguards", "safeguard_dependencies", "hazop_rows", "hazop_row_safeguards",
    "hazop_recommendations", "risk_rule_sets", "users", "prompt_templates",
    "documents", "document_assets", "golden_items",
)


class AdminService:
    """
    Service for admin operations.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize AdminService with a DB session."""
        self.db = db

    async def ingest(self, user: CurrentUser) -> JSONResponse:
        """Re-chunk data/corpus/*.md, embed, upsert into Chroma; idempotent by content hash.

        Chunk rows keep their ids across re-ingests (citations point at them):
        an unchanged chunk is skipped, a changed one is updated in place.
        """
        corpus_dir = env.demo_data_path / "corpus"
        if not corpus_dir.is_dir():
            return response_error(f"Corpus directory {corpus_dir} not found", code=404)

        docs_repo = DocumentRepository(self.db)
        chunks_repo = DocumentChunkRepository(self.db)
        links_repo = DocumentAssetRepository(self.db)
        assets = {a.tag: a.id for a in await AssetRepository(self.db).list_by_unit(limit=1000)}
        embedding_model = env.gemini_embedding_model if env.llm_enabled else "bm25-only"
        stats = {"documents": 0, "chunks": 0, "inserted": 0, "updated": 0, "skipped": 0, "removed": 0}

        for doc in load_corpus(corpus_dir):
            document = await docs_repo.get_by_code_revision(doc.doc_code, doc.revision)
            if not document:
                document = Document(doc_code=doc.doc_code, revision=doc.revision, title=doc.title, type=DocType(doc.type))
                await docs_repo.add(document)
            document.title = doc.title
            document.type = DocType(doc.type)
            document.effective_date = doc.effective_date
            document.is_current = doc.is_current
            document.origin = DataOrigin(doc.origin)
            document.storage_uri = f"data/corpus/{doc.path.name}"
            await links_repo.replace_for_document(document.id, [assets[t] for t in doc.asset_tags if t in assets])
            stats["documents"] += 1

            for chunk in doc.chunks:
                stats["chunks"] += 1
                point_id = str(uuid.uuid5(POINT_NAMESPACE, f"{doc.doc_code}:{doc.revision}:{chunk.chunk_index}:{chunk.content_hash}"))
                existing = await chunks_repo.get_by_document_index(document.id, chunk.chunk_index)
                if existing and existing.vector_id == point_id:
                    stats["skipped"] += 1
                    continue
                if existing:
                    existing.text, existing.section, existing.token_count = chunk.text, chunk.section, chunk.token_count
                    existing.vector_id, existing.embedding_model = point_id, embedding_model
                    stats["updated"] += 1
                else:
                    self.db.add(DocumentChunk(
                        document_id=document.id, chunk_index=chunk.chunk_index, text=chunk.text,
                        section=chunk.section, token_count=chunk.token_count,
                        vector_id=point_id, embedding_model=embedding_model,
                    ))
                    stats["inserted"] += 1
            await self.db.flush()

            extra = [c for c in await chunks_repo.list_by_document(document.id) if c.chunk_index >= len(doc.chunks)]
            cited = await CitationRepository(self.db).cited_chunk_ids([c.id for c in extra])
            for chunk_row in extra:
                if chunk_row.id not in cited:
                    await self.db.delete(chunk_row)
                    stats["removed"] += 1
        await self.db.commit()

        retrieval_index.invalidate()
        await retrieval_index.ensure_loaded()
        vectors = await self._index_vectors()
        return response_success(
            {**stats, "indexed_documents": retrieval_index.document_count, **vectors},
            msg="Accepted",
            code=202,
        )

    async def _index_vectors(self) -> dict:
        """Sync Chroma with the current chunks (dense half of the hybrid index); stale vectors are removed."""
        if not env.llm_enabled:
            return {"embedded": 0, "vector_store": "disabled (LLM_ENABLED=false): BM25 only"}
        try:
            return {**await retrieval_index.sync_vectors(), "vector_store": chroma_store.describe()}
        except Exception:
            logger.exception("Chroma sync failed")
        if not await retrieval_index.ensure_vectors():
            return {"embedded": 0, "vector_store": "embedding failed: BM25 only"}
        return {"embedded": len(retrieval_index.vectors), "vector_store": "chroma sync failed: in-process vectors"}

    async def seed(self, user: CurrentUser) -> JSONResponse:
        """Load asset model, HAZOP, rule set and demo users; 409 if a replay is running.

        Runs the package's data/sql/seed.sql, which is idempotent (deterministic
        ids, ON CONFLICT DO NOTHING) and wraps itself in one transaction.
        """
        active = await ReplayRunRepository(self.db).get_active()
        if active and replay_manager.state_of(active) == RUNNING:
            return response_error("A replay is running; pause or reset it before seeding", code=409)

        seed_path = env.demo_data_path / "sql" / "seed.sql"
        if not seed_path.is_file():
            return response_error(f"Seed file {seed_path} not found", code=404)

        conn = await asyncpg.connect(
            host=env.db_host, port=env.db_port, user=env.db_user,
            password=env.db_pass, database=env.db_name,
        )
        try:
            await conn.execute(seed_path.read_text(encoding="utf-8"))
            counts = {table: await conn.fetchval(f'SELECT count(*) FROM "{table}"') for table in SEED_COUNT_TABLES}
        finally:
            await conn.close()
        retrieval_index.invalidate()
        return response_success({"seed_file": f"data/sql/{seed_path.name}", "tables": counts}, msg="Seeded")

    async def get_agent_graph(self, agent_name: str) -> HTMLResponse:
        """Render the agent graph with render_graph_html; 404 unless APP_ENV=development."""
        if env.app_env.lower() != "development":
            return response_error("Not found", code=404)
        if agent_name == "knowledge":
            from app.agents.knowledge.graph import build_knowledge_graph
            graph, title = build_knowledge_graph(), "Knowledge agent · kb.v1"
        else:
            from app.agents.red_team.graph import build_red_team_graph
            graph, title = build_red_team_graph(), "Red Team agent · redteam.v1"
        return HTMLResponse(render_graph_html(graph, title))
